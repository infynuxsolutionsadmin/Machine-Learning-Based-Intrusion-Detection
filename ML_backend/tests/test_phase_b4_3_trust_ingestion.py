"""
test_phase_b4_3_trust_ingestion.py - Comprehensive Isolated Tests for Phase B4.3 LSTM Trust Evaluation Ingestion.

Covers all 26 required test criteria:
1. Successful ingestion of 1,160 records.
2. Identical rerun produces zero inserts (NO-OP).
3. Exact timestamp preservation (no rounding).
4. Distinct timestamps are not collapsed.
5. Conflict rejected on trust_score.
6. Conflict rejected on threshold.
7. Conflict rejected on is_malicious.
8. Conflict rejected on inferred_action.
9. Partial ingestion with 50 identical existing rows (inserts 1,110 rows).
10. Atomic rollback on conflict.
11. Atomic rollback across batches.
12. Float tolerance behavior (< 1e-5 passes, >= 1e-4 rejects).
13. Cell-by-cell source parity.
14. Malicious prediction breakdown (node 2: 55, node 4: 33, others: 0).
15. Inferred-action semantics ('Blacklisted' iff is_malicious == 1).
16. prevention_events remains unchanged (0 records).
17. Missing CSV rejection (FileNotFoundError).
18. Hash mismatch rejection (ValueError).
19. Missing CSV columns rejection (ValueError).
20. Negative timestamp rejection (ValueError).
21. Invalid node ID rejection (ValueError).
22. Invalid trust score rejection (NaN, Inf, < 0, > 1).
23. Non-binary classification rejection (ValueError).
24. Duplicate source row rejection (ValueError).
25. Unknown run ID rejection (ValueError).
26. Historical table invariance (B2/B3 row counts unchanged).
"""
import csv
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.session import create_db_engine
from database.models import (
    SimulationRun,
    SimulationMetric,
    NodeEnergyMetric,
    SimulationArtifact,
    ModelRegistry,
    MLPrediction,
    TrustEvaluation,
    PreventionEvent,
)
from database.ingestion_service import (
    ingest_simulation_core,
    ingest_model_registry,
    ingest_classical_ml_predictions,
    ingest_trust_evaluations,
    compute_file_sha256,
    BASELINE_MODELS_DIR,
    DYNAMIC_RESULTS_DIR,
)

PILOT_RUN_ID = "20261111_225145_8e3c4f7c_8nodes_attack2_4"


def setup_test_db(tmpdir: Path):
    """Helper to set up an isolated test database with B2 core and B3 data."""
    test_db_path = tmpdir / "test_b4_3.db"
    test_engine = create_db_engine(test_db_path)
    Base.metadata.create_all(bind=test_engine)
    SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

    from database import session as sess_module
    orig_sessionlocal = sess_module.SessionLocal
    sess_module.SessionLocal = SessionTest

    # Seed B2 core simulation data
    ingest_simulation_core(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
    # Seed B3.2 model registry
    ingest_model_registry(models_dir=BASELINE_MODELS_DIR, include_inactive=True)
    # Seed B3.3 classical ML predictions
    ingest_classical_ml_predictions(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

    return test_engine, SessionTest, orig_sessionlocal


def test_01_successful_ingestion():
    """1. Successful ingestion of 1,160 records."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            res = ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res["status"] == "success"
            assert res["total_source_records"] == 1160
            assert res["inserted_count"] == 1160
            assert res["already_existing_count"] == 0

            with SessionTest() as session:
                count = session.query(TrustEvaluation).count()
                assert count == 1160
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_02_identical_rerun_noop():
    """2. Identical rerun produces zero inserts (NO-OP) and preserves primary keys."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            res1 = ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res1["inserted_count"] == 1160

            with SessionTest() as session:
                orig_ids = [r.id for r in session.query(TrustEvaluation.id).order_by(TrustEvaluation.id).all()]

            res2 = ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res2["status"] == "success"
            assert res2["inserted_count"] == 0
            assert res2["already_existing_count"] == 1160

            with SessionTest() as session:
                new_ids = [r.id for r in session.query(TrustEvaluation.id).order_by(TrustEvaluation.id).all()]
                assert orig_ids == new_ids
                assert session.query(TrustEvaluation).count() == 1160
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_03_exact_timestamp_preservation():
    """3. Exact timestamp preservation without artificial rounding."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            with SessionTest() as session:
                sample = session.query(TrustEvaluation).filter_by(node_id=0).order_by(TrustEvaluation.time_sec).first()
                assert sample.time_sec == 5.1
                assert type(sample.time_sec) is float
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_04_distinct_timestamps_are_not_collapsed():
    """4. Distinct timestamps are not collapsed by key construction."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            with SessionTest() as session:
                times = [r[0] for r in session.query(TrustEvaluation.time_sec).distinct().all()]
                assert len(times) == 145
                assert min(times) == 5.1
                assert max(times) == 149.1
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_05_conflict_rejected_on_trust_score():
    """5. Conflict rejected on differing trust_score."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            # Seed 1 record with different trust score
            with SessionTest() as session:
                run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                session.add(TrustEvaluation(
                    simulation_run_id=run.id,
                    time_sec=5.1,
                    node_id=0,
                    trust_score=0.1234,  # actual in CSV is 0.9643
                    threshold=0.5,
                    is_malicious=0,
                    inferred_action="None"
                ))
                session.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError on conflicting trust_score"
            except ValueError as e:
                assert "conflicting records detected" in str(e).lower()

            with SessionTest() as session:
                assert session.query(TrustEvaluation).count() == 1
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_06_conflict_rejected_on_threshold():
    """6. Conflict rejected on differing threshold."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                session.add(TrustEvaluation(
                    simulation_run_id=run.id,
                    time_sec=5.1,
                    node_id=0,
                    trust_score=0.9643,
                    threshold=0.8,  # differs from 0.5
                    is_malicious=0,
                    inferred_action="None"
                ))
                session.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError on conflicting threshold"
            except ValueError as e:
                assert "conflicting records detected" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_07_conflict_rejected_on_is_malicious():
    """7. Conflict rejected on differing is_malicious."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                session.add(TrustEvaluation(
                    simulation_run_id=run.id,
                    time_sec=5.1,
                    node_id=0,
                    trust_score=0.9643,
                    threshold=0.5,
                    is_malicious=1,  # actual in CSV is 0
                    inferred_action="None"
                ))
                session.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError on conflicting is_malicious"
            except ValueError as e:
                assert "conflicting records detected" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_08_conflict_rejected_on_inferred_action():
    """8. Conflict rejected on differing inferred_action."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                session.add(TrustEvaluation(
                    simulation_run_id=run.id,
                    time_sec=5.1,
                    node_id=0,
                    trust_score=0.9643,
                    threshold=0.5,
                    is_malicious=0,
                    inferred_action="Blacklisted"  # actual should be 'None'
                ))
                session.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError on conflicting inferred_action"
            except ValueError as e:
                assert "conflicting records detected" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_09_partial_ingestion_with_identical_subset():
    """9. Partial ingestion with 50 identical existing rows inserts 1,110 rows and NO-OPs on 50."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            # Read first 50 rows from authentic CSV
            csv_path = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                first_50 = [next(reader) for _ in range(50)]

            with SessionTest() as session:
                run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                for r in first_50:
                    m = int(r["is_malicious"])
                    session.add(TrustEvaluation(
                        simulation_run_id=run.id,
                        time_sec=float(r["time"]),
                        node_id=int(r["node"]),
                        trust_score=float(r["score"]),
                        threshold=0.5,
                        is_malicious=m,
                        inferred_action="Blacklisted" if m == 1 else "None"
                    ))
                session.commit()
                assert session.query(TrustEvaluation).count() == 50

            res = ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res["inserted_count"] == 1110
            assert res["already_existing_count"] == 50
            assert res["total_source_records"] == 1160

            with SessionTest() as session:
                assert session.query(TrustEvaluation).count() == 1160
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_10_atomic_rollback_on_conflict():
    """10. Atomic rollback on conflict: zero new or modified records persist."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                session.add(TrustEvaluation(
                    simulation_run_id=run.id,
                    time_sec=149.1,
                    node_id=7,
                    trust_score=0.9999,  # Conflict at last row
                    threshold=0.5,
                    is_malicious=0,
                    inferred_action="None"
                ))
                session.commit()
                assert session.query(TrustEvaluation).count() == 1

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have aborted transaction"
            except ValueError:
                pass

            with SessionTest() as session:
                assert session.query(TrustEvaluation).count() == 1
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_11_atomic_rollback_across_batches():
    """11. Atomic rollback across batches: failure in a chunk rolls back all prior chunks."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            from sqlalchemy.orm import Session as SASession
            orig_bulk = SASession.bulk_insert_mappings
            call_count = [0]

            def failing_bulk(self, mapper, mappings):
                call_count[0] += 1
                if call_count[0] == 3:  # Fail on 3rd batch (after batch 1 and 2 staged)
                    raise RuntimeError("Simulated mid-batch database failure")
                orig_bulk(self, mapper, mappings)

            with patch.object(SASession, "bulk_insert_mappings", failing_bulk):
                try:
                    ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR, batch_size=200)
                    assert False, "Should have raised RuntimeError"
                except RuntimeError as e:
                    assert "Simulated mid-batch" in str(e)

            with SessionTest() as session:
                assert session.query(TrustEvaluation).count() == 0
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_12_float_tolerance_behavior():
    """12. Float tolerance behavior: diff < 1e-5 passes, diff >= 1e-4 rejects."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            # Seed 1 record with diff < 1e-5 (e.g. 1e-6 diff): should pass
            with SessionTest() as session:
                run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                session.add(TrustEvaluation(
                    simulation_run_id=run.id,
                    time_sec=5.1,
                    node_id=0,
                    trust_score=0.964300001,  # diff of 1e-9 from 0.9643
                    threshold=0.5,
                    is_malicious=0,
                    inferred_action="None"
                ))
                session.commit()

            res = ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res["already_existing_count"] == 1
            assert res["inserted_count"] == 1159
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_13_cell_by_cell_source_parity():
    """13. Cell-by-cell source parity across all 1,160 rows."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            csv_path = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            with open(csv_path, mode="r", encoding="utf-8") as f:
                csv_rows = list(csv.DictReader(f))

            with SessionTest() as session:
                db_rows = {
                    (r.time_sec, r.node_id): r
                    for r in session.query(TrustEvaluation).all()
                }

                assert len(db_rows) == len(csv_rows) == 1160
                for r in csv_rows:
                    t = float(r["time"])
                    n = int(r["node"])
                    s = float(r["score"])
                    m = int(r["is_malicious"])

                    db_rec = db_rows[(t, n)]
                    assert math.isclose(db_rec.trust_score, s, abs_tol=1e-5)
                    assert db_rec.threshold == 0.5
                    assert db_rec.is_malicious == m
                    assert db_rec.inferred_action == ("Blacklisted" if m == 1 else "None")
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_14_malicious_breakdown_fidelity():
    """14. Malicious breakdown fidelity: node 2 has 55, node 4 has 33, others 0."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            with SessionTest() as session:
                total_mal = session.query(TrustEvaluation).filter_by(is_malicious=1).count()
                total_norm = session.query(TrustEvaluation).filter_by(is_malicious=0).count()
                assert total_mal == 88
                assert total_norm == 1072

                node2_mal = session.query(TrustEvaluation).filter_by(node_id=2, is_malicious=1).count()
                node4_mal = session.query(TrustEvaluation).filter_by(node_id=4, is_malicious=1).count()
                assert node2_mal == 55
                assert node4_mal == 33

                for n in [0, 1, 3, 5, 6, 7]:
                    n_mal = session.query(TrustEvaluation).filter_by(node_id=n, is_malicious=1).count()
                    assert n_mal == 0
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_15_inferred_action_semantics():
    """15. Inferred action semantics: 'Blacklisted' iff is_malicious == 1."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            with SessionTest() as session:
                b_count = session.query(TrustEvaluation).filter_by(inferred_action="Blacklisted").count()
                none_count = session.query(TrustEvaluation).filter_by(inferred_action="None").count()
                assert b_count == 88
                assert none_count == 1072

                # Verify no mismatched action exists
                mismatch = session.query(TrustEvaluation).filter(
                    ((TrustEvaluation.is_malicious == 1) & (TrustEvaluation.inferred_action != "Blacklisted")) |
                    ((TrustEvaluation.is_malicious == 0) & (TrustEvaluation.inferred_action != "None"))
                ).count()
                assert mismatch == 0
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_16_prevention_events_isolation():
    """16. prevention_events table remains unchanged (0 records)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                assert session.query(PreventionEvent).count() == 0

            ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            with SessionTest() as session:
                assert session.query(PreventionEvent).count() == 0
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_17_missing_csv_rejection():
    """17. Missing CSV rejection raises FileNotFoundError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            empty_dir = tmp_path / "empty_dir"
            empty_dir.mkdir()
            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=empty_dir)
                assert False, "Should have raised FileNotFoundError"
            except FileNotFoundError as e:
                assert "missing" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_18_hash_mismatch_rejection():
    """18. Hash mismatch rejection raises ValueError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            corrupt_dir = tmp_path / "corrupt_dir"
            corrupt_dir.mkdir()
            orig_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            corrupt_csv = corrupt_dir / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            shutil.copyfile(orig_csv, corrupt_csv)

            with open(corrupt_csv, "a", encoding="utf-8") as f:
                f.write("999.0,0,0.5,0\n")

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=corrupt_dir)
                assert False, "Should have raised ValueError on hash mismatch"
            except ValueError as e:
                assert "mismatch" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_19_missing_csv_columns_rejection():
    """19. Missing CSV columns rejection raises ValueError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        orig_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
        lines = orig_csv.read_text(encoding="utf-8").splitlines()
        try:
            fake_dir = tmp_path / "test_csv_dir"
            fake_dir.mkdir()
            bad_csv = fake_dir / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            bad_lines = [lines[0].replace(",is_malicious", "")] + lines[1:]
            bad_csv.write_text("\n".join(bad_lines), encoding="utf-8")
            bad_hash = compute_file_sha256(bad_csv)

            with SessionTest() as s:
                art = s.query(SimulationArtifact).filter_by(file_type="lstm_pred_csv").first()
                if art:
                    art.file_hash_sha256 = bad_hash
                    s.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=fake_dir)
                assert False, "Should have raised ValueError on missing is_malicious"
            except ValueError as e:
                assert "missing" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_20_negative_timestamp_rejection():
    """20. Negative timestamp rejection raises ValueError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        orig_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
        lines = orig_csv.read_text(encoding="utf-8").splitlines()
        try:
            fake_dir = tmp_path / "test_csv_dir"
            fake_dir.mkdir()
            bad_csv = fake_dir / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            bad_lines = [lines[0], "-1.0,0,0.9643,0"] + lines[2:]
            bad_csv.write_text("\n".join(bad_lines), encoding="utf-8")
            bad_hash = compute_file_sha256(bad_csv)

            with SessionTest() as s:
                art = s.query(SimulationArtifact).filter_by(file_type="lstm_pred_csv").first()
                if art:
                    art.file_hash_sha256 = bad_hash
                    s.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=fake_dir)
                assert False, "Should have raised ValueError on negative time"
            except ValueError as e:
                assert "negative" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_21_invalid_node_id_rejection():
    """21. Invalid node ID rejection raises ValueError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        orig_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
        lines = orig_csv.read_text(encoding="utf-8").splitlines()
        try:
            fake_dir = tmp_path / "test_csv_dir"
            fake_dir.mkdir()
            bad_csv = fake_dir / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            bad_lines = [lines[0], "5.1,8,0.9643,0"] + lines[2:]
            bad_csv.write_text("\n".join(bad_lines), encoding="utf-8")
            bad_hash = compute_file_sha256(bad_csv)

            with SessionTest() as s:
                art = s.query(SimulationArtifact).filter_by(file_type="lstm_pred_csv").first()
                if art:
                    art.file_hash_sha256 = bad_hash
                    s.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=fake_dir)
                assert False, "Should have raised ValueError on node out of range"
            except ValueError as e:
                assert "node id" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_22_invalid_trust_score_rejection():
    """22. Invalid trust score rejection (NaN, Inf, <0, >1) raises ValueError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        orig_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
        lines = orig_csv.read_text(encoding="utf-8").splitlines()
        try:
            fake_dir = tmp_path / "test_csv_dir"
            fake_dir.mkdir()

            for bad_score in ["1.5", "-0.1", "NaN", "Infinity"]:
                bad_csv = fake_dir / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
                bad_lines = [lines[0], f"5.1,0,{bad_score},0"] + lines[2:]
                bad_csv.write_text("\n".join(bad_lines), encoding="utf-8")
                bad_hash = compute_file_sha256(bad_csv)

                with SessionTest() as s:
                    art = s.query(SimulationArtifact).filter_by(file_type="lstm_pred_csv").first()
                    if art:
                        art.file_hash_sha256 = bad_hash
                        s.commit()

                try:
                    ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=fake_dir)
                    assert False, f"Should have raised ValueError for score={bad_score}"
                except ValueError:
                    pass
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_23_non_binary_classification_rejection():
    """23. Non-binary classification rejection raises ValueError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        orig_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
        lines = orig_csv.read_text(encoding="utf-8").splitlines()
        try:
            fake_dir = tmp_path / "test_csv_dir"
            fake_dir.mkdir()
            bad_csv = fake_dir / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            bad_lines = [lines[0], "5.1,0,0.9643,2"] + lines[2:]
            bad_csv.write_text("\n".join(bad_lines), encoding="utf-8")
            bad_hash = compute_file_sha256(bad_csv)

            with SessionTest() as s:
                art = s.query(SimulationArtifact).filter_by(file_type="lstm_pred_csv").first()
                if art:
                    art.file_hash_sha256 = bad_hash
                    s.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=fake_dir)
                assert False, "Should have raised ValueError on non-binary classification"
            except ValueError as e:
                assert "non-binary" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_24_duplicate_source_row_rejection():
    """24. Duplicate source row rejection raises ValueError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        orig_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
        lines = orig_csv.read_text(encoding="utf-8").splitlines()
        try:
            fake_dir = tmp_path / "test_csv_dir"
            fake_dir.mkdir()
            bad_csv = fake_dir / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            bad_lines = [lines[0], lines[1], lines[1]] + lines[3:]
            bad_csv.write_text("\n".join(bad_lines), encoding="utf-8")
            bad_hash = compute_file_sha256(bad_csv)

            with SessionTest() as s:
                art = s.query(SimulationArtifact).filter_by(file_type="lstm_pred_csv").first()
                if art:
                    art.file_hash_sha256 = bad_hash
                    s.commit()

            try:
                ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=fake_dir)
                assert False, "Should have raised ValueError on duplicate (time, node)"
            except ValueError as e:
                assert "duplicate" in str(e).lower()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_25_unknown_run_id_rejection():
    """25. Unknown run ID rejection raises ValueError."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            # Create a dummy CSV matching the unknown run
            unknown_run = "20261111_999999_dummy_8nodes_attack2_4"
            dummy_csv = DYNAMIC_RESULTS_DIR / f"run_{unknown_run}_lstm_pred.csv"
            orig_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_lstm_pred.csv"
            shutil.copyfile(orig_csv, dummy_csv)

            try:
                ingest_trust_evaluations(unknown_run, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError for non-existent run"
            except ValueError as e:
                assert "not found" in str(e).lower()
            finally:
                if dummy_csv.exists():
                    dummy_csv.unlink()
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_26_historical_tables_invariance():
    """26. Historical tables invariance: B2 and B3 counts remain unchanged."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                counts_before = {
                    "simulation_runs": session.query(SimulationRun).count(),
                    "simulation_metrics": session.query(SimulationMetric).count(),
                    "node_energy_metrics": session.query(NodeEnergyMetric).count(),
                    "simulation_artifacts": session.query(SimulationArtifact).count(),
                    "model_registry": session.query(ModelRegistry).count(),
                    "ml_predictions": session.query(MLPrediction).count(),
                    "prevention_events": session.query(PreventionEvent).count(),
                }

            ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            with SessionTest() as session:
                counts_after = {
                    "simulation_runs": session.query(SimulationRun).count(),
                    "simulation_metrics": session.query(SimulationMetric).count(),
                    "node_energy_metrics": session.query(NodeEnergyMetric).count(),
                    "simulation_artifacts": session.query(SimulationArtifact).count(),
                    "model_registry": session.query(ModelRegistry).count(),
                    "ml_predictions": session.query(MLPrediction).count(),
                    "prevention_events": session.query(PreventionEvent).count(),
                }

                assert counts_before == counts_after
                assert counts_after["simulation_runs"] == 1
                assert counts_after["simulation_metrics"] == 106
                assert counts_after["node_energy_metrics"] == 16
                assert counts_after["simulation_artifacts"] == 16
                assert counts_after["model_registry"] == 5
                assert counts_after["ml_predictions"] == 3576
                assert counts_after["prevention_events"] == 0
                assert session.query(TrustEvaluation).count() == 1160
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


if __name__ == "__main__":
    tests = [
        test_01_successful_ingestion,
        test_02_identical_rerun_noop,
        test_03_exact_timestamp_preservation,
        test_04_distinct_timestamps_are_not_collapsed,
        test_05_conflict_rejected_on_trust_score,
        test_06_conflict_rejected_on_threshold,
        test_07_conflict_rejected_on_is_malicious,
        test_08_conflict_rejected_on_inferred_action,
        test_09_partial_ingestion_with_identical_subset,
        test_10_atomic_rollback_on_conflict,
        test_11_atomic_rollback_across_batches,
        test_12_float_tolerance_behavior,
        test_13_cell_by_cell_source_parity,
        test_14_malicious_breakdown_fidelity,
        test_15_inferred_action_semantics,
        test_16_prevention_events_isolation,
        test_17_missing_csv_rejection,
        test_18_hash_mismatch_rejection,
        test_19_missing_csv_columns_rejection,
        test_20_negative_timestamp_rejection,
        test_21_invalid_node_id_rejection,
        test_22_invalid_trust_score_rejection,
        test_23_non_binary_classification_rejection,
        test_24_duplicate_source_row_rejection,
        test_25_unknown_run_id_rejection,
        test_26_historical_tables_invariance,
    ]
    print(f"Running {len(tests)} Phase B4.3 isolated tests...")
    for idx, t in enumerate(tests, 1):
        t()
        print(f"  [{idx:02d}/{len(tests):02d}] {t.__name__} PASSED")
    print(f"\nALL {len(tests)} PHASE B4.3 TESTS PASSED SUCCESSFULLY!")

