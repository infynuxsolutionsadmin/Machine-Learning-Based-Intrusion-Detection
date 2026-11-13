"""
test_phase_b5_3_routing_ingestion.py - Comprehensive Isolated Tests for Phase B5.3 Routing Records Ingestion.

Covers all 18 required test criteria:
1. Valid Pass 2 JSON mapping.
2. Dynamic simulation-run resolution.
3. Artifact SHA-256 verification.
4. Invalid or missing JSON keys.
5. Invalid hop sequence.
6. Incorrect hop count.
7. Unknown malicious-node metadata.
8. Malicious-node detection.
9. First ingestion inserts exactly one record.
10. Identical rerun inserts zero records.
11. Existing primary key remains unchanged after rerun.
12. Conflicting existing record is rejected.
13. Missing simulation run.
14. Missing source file.
15. Artifact hash mismatch.
16. Transaction rollback on failure.
17. No Pass 1 synthetic record is created.
18. Existing B2/B3/B4 data remains unchanged.
"""
import copy
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

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
    RoutingRecord,
    PreventionEvent,
)
from database.ingestion_service import (
    ingest_simulation_core,
    ingest_model_registry,
    ingest_classical_ml_predictions,
    ingest_trust_evaluations,
    ingest_routing_records,
    compute_file_sha256,
    BASELINE_MODELS_DIR,
    DYNAMIC_RESULTS_DIR,
)

PILOT_RUN_ID = "20261111_225145_8e3c4f7c_8nodes_attack2_4"


def setup_test_db(tmpdir: Path):
    """Helper to set up an isolated test database with B2, B3, and B4 data."""
    test_db_path = tmpdir / "test_b5_3.db"
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
    # Seed B4.3 LSTM trust evaluations
    ingest_trust_evaluations(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

    # Ensure pilot run metadata matches live database ground-truth
    with SessionTest() as session:
        run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).first()
        if run:
            run.num_malicious = 2
            run.ground_truth_malicious = json.dumps([2, 4])
            session.commit()

    return test_engine, SessionTest, orig_sessionlocal


def test_01_valid_pass2_json_mapping():
    """1. Valid Pass 2 JSON mapping."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            res = ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res["status"] == "success"
            assert res["inserted"] == 1

            with SessionTest() as session:
                rec = session.query(RoutingRecord).filter_by(simulation_run_id=res["simulation_run_id"]).first()
                assert rec is not None
                assert rec.phase == "mitigated_pass2"
                assert rec.source_node == 0
                assert rec.dest_node == 7
                assert rec.hop_count == 3
                assert rec.route_available is True
                assert rec.destination_reached is True
                assert rec.has_malicious_node is False
                assert rec.notes is None

                hops = json.loads(rec.hops_json)
                assert len(hops) == 4
                assert hops[0] == {"node_id": 0, "time": 2.0, "ip": "10.1.1.1"}
                assert hops[1] == {"node_id": 6, "time": 2.1, "ip": "10.1.1.7"}
                assert hops[2] == {"node_id": 3, "time": 2.2, "ip": "10.1.1.4"}
                assert hops[3] == {"node_id": 7, "time": 2.3, "ip": "10.1.1.8"}
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_02_dynamic_simulation_run_resolution():
    """2. Dynamic simulation-run resolution (does not hardcode id=1)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            # Create a second simulation run
            custom_run_id = "20261112_100000_secondary_run"
            with SessionTest() as session:
                run2 = SimulationRun(
                    run_id=custom_run_id,
                    protocol="AODV",
                    num_nodes=8,
                    num_malicious=2,
                    ground_truth_malicious=json.dumps([2, 4]),
                    simulation_status="completed",
                    persistence_status="completed",
                )
                session.add(run2)
                session.commit()
                run2_id = run2.id
                assert run2_id != 1

                # Copy source routing file for this second run
                src_json = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_routing.json"
                with open(src_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["run_id"] = custom_run_id
                target_json = tmp_path / f"run_{custom_run_id}_routing.json"
                with open(target_json, "w", encoding="utf-8") as f:
                    json.dump(data, f)

                # Register artifact for run2
                h = compute_file_sha256(target_json)
                art = SimulationArtifact(
                    simulation_run_id=run2_id,
                    file_type="routing_json_p2",
                    file_path=str(target_json),
                    file_size_bytes=target_json.stat().st_size,
                    file_hash_sha256=h,
                )
                session.add(art)
                session.commit()

            # Ingest for custom_run_id
            res = ingest_routing_records(custom_run_id, dynamic_dir=tmp_path)
            assert res["status"] == "success"
            assert res["simulation_run_id"] == run2_id
            assert res["inserted"] == 1

            with SessionTest() as session:
                rec = session.query(RoutingRecord).filter_by(simulation_run_id=run2_id).first()
                assert rec is not None
                assert rec.simulation_run_id == run2_id
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_03_artifact_sha256_verification():
    """3. Artifact SHA-256 verification."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                art = (
                    session.query(SimulationArtifact)
                    .filter_by(file_type="routing_json_p2")
                    .first()
                )
                assert art is not None
                src_path = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_routing.json"
                actual_h = compute_file_sha256(src_path)
                assert art.file_hash_sha256 == actual_h
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_04_invalid_or_missing_json_keys():
    """4. Invalid or missing JSON keys."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            # Create corrupted json missing hops
            bad_json = tmp_path / f"run_{PILOT_RUN_ID}_routing.json"
            bad_data = {
                "run_id": PILOT_RUN_ID,
                "source_node": 0,
                "destination_node": 7,
                "hop_count": 3,
                "route_available": True,
                "destination_reached": True,
                # "hops" is missing
            }
            with open(bad_json, "w", encoding="utf-8") as f:
                json.dump(bad_data, f)

            # Update artifact hash in db so hash check passes and key check triggers
            h = compute_file_sha256(bad_json)
            with SessionTest() as session:
                art = session.query(SimulationArtifact).filter_by(file_type="routing_json_p2").first()
                art.file_hash_sha256 = h
                session.commit()

            try:
                ingest_routing_records(PILOT_RUN_ID, dynamic_dir=tmp_path)
                assert False, "Should have raised ValueError on missing keys"
            except ValueError as e:
                assert "missing required keys" in str(e)
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_05_invalid_hop_sequence():
    """5. Invalid hop sequence (first hop != source, or last hop != dest)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            bad_json = tmp_path / f"run_{PILOT_RUN_ID}_routing.json"
            src_json = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_routing.json"
            with open(src_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Alter first hop
            data["hops"][0]["node_id"] = 1  # source_node is 0

            with open(bad_json, "w", encoding="utf-8") as f:
                json.dump(data, f)

            h = compute_file_sha256(bad_json)
            with SessionTest() as session:
                art = session.query(SimulationArtifact).filter_by(file_type="routing_json_p2").first()
                art.file_hash_sha256 = h
                session.commit()

            try:
                ingest_routing_records(PILOT_RUN_ID, dynamic_dir=tmp_path)
                assert False, "Should have raised ValueError on invalid hop sequence"
            except ValueError as e:
                assert "First hop node_id" in str(e)
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_06_incorrect_hop_count():
    """6. Incorrect hop count."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            bad_json = tmp_path / f"run_{PILOT_RUN_ID}_routing.json"
            src_json = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_routing.json"
            with open(src_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["hop_count"] = 5  # len(hops) is 4 -> hop_count should be 3

            with open(bad_json, "w", encoding="utf-8") as f:
                json.dump(data, f)

            h = compute_file_sha256(bad_json)
            with SessionTest() as session:
                art = session.query(SimulationArtifact).filter_by(file_type="routing_json_p2").first()
                art.file_hash_sha256 = h
                session.commit()

            try:
                ingest_routing_records(PILOT_RUN_ID, dynamic_dir=tmp_path)
                assert False, "Should have raised ValueError on incorrect hop_count"
            except ValueError as e:
                assert "does not match len(hops) - 1" in str(e)
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_07_unknown_malicious_node_metadata():
    """7. Unknown malicious-node metadata (num_malicious > 0 but ground_truth_malicious is None)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                run = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).first()
                run.ground_truth_malicious = None
                session.commit()

            try:
                ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError on unknown malicious metadata"
            except ValueError as e:
                assert "Cannot determine authoritative malicious nodes" in str(e)
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_08_malicious_node_detection():
    """8. Malicious-node detection (hops containing malicious node -> has_malicious_node = True)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            src_json = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_routing.json"
            with open(src_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Substitute node 6 with attacker node 2
            data["hops"][1]["node_id"] = 2
            data["hops"][1]["ip"] = "10.1.1.3"

            mod_json = tmp_path / f"run_{PILOT_RUN_ID}_routing.json"
            with open(mod_json, "w", encoding="utf-8") as f:
                json.dump(data, f)

            h = compute_file_sha256(mod_json)
            with SessionTest() as session:
                art = session.query(SimulationArtifact).filter_by(file_type="routing_json_p2").first()
                art.file_hash_sha256 = h
                session.commit()

            res = ingest_routing_records(PILOT_RUN_ID, dynamic_dir=tmp_path)
            assert res["status"] == "success"

            with SessionTest() as session:
                rec = session.query(RoutingRecord).filter_by(simulation_run_id=res["simulation_run_id"]).first()
                assert rec.has_malicious_node is True
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_09_first_ingestion_inserts_exactly_one_record():
    """9. First ingestion inserts exactly one record."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                assert session.query(RoutingRecord).count() == 0

            res = ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res["status"] == "success"
            assert res["inserted"] == 1
            assert res["existing"] == 0

            with SessionTest() as session:
                assert session.query(RoutingRecord).count() == 1
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_10_identical_rerun_inserts_zero_records():
    """10. Identical rerun inserts zero records."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            res1 = ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res1["inserted"] == 1

            res2 = ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res2["status"] == "ALREADY_INGESTED"
            assert res2["inserted"] == 0
            assert res2["existing"] == 1

            with SessionTest() as session:
                assert session.query(RoutingRecord).count() == 1
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_11_existing_primary_key_unchanged_after_rerun():
    """11. Existing primary key remains unchanged after rerun."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            res1 = ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            pk1 = res1["routing_record_id"]

            res2 = ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            pk2 = res2["routing_record_id"]

            assert pk1 == pk2

            with SessionTest() as session:
                records = session.query(RoutingRecord).all()
                assert len(records) == 1
                assert records[0].id == pk1
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_12_conflicting_existing_record_rejected():
    """12. Conflicting existing record is rejected."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            # Mutate existing record in DB
            with SessionTest() as session:
                rec = session.query(RoutingRecord).first()
                rec.destination_reached = False
                session.commit()

            # Attempt rerun -> must raise conflict
            try:
                ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError on conflicting existing record"
            except ValueError as e:
                assert "Conflicting routing record" in str(e)
                assert "destination_reached" in str(e)
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_13_missing_simulation_run():
    """13. Missing simulation run."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            try:
                ingest_routing_records("nonexistent_run_99999", dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError for missing simulation run"
            except ValueError as e:
                assert "not found in simulation_runs" in str(e)
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_14_missing_source_file():
    """14. Missing source file."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            empty_dir = tmp_path / "empty_dir"
            empty_dir.mkdir()
            try:
                ingest_routing_records(PILOT_RUN_ID, dynamic_dir=empty_dir)
                assert False, "Should have raised FileNotFoundError for missing routing file"
            except FileNotFoundError as e:
                assert "not found at" in str(e)
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_15_artifact_hash_mismatch():
    """15. Artifact hash mismatch."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                art = session.query(SimulationArtifact).filter_by(file_type="routing_json_p2").first()
                art.file_hash_sha256 = "0" * 64
                session.commit()

            try:
                ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Should have raised ValueError on artifact hash mismatch"
            except ValueError as e:
                assert "Artifact SHA-256 mismatch" in str(e)
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_16_transaction_rollback_on_failure():
    """16. Transaction rollback on failure."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            # Create a file that fails validation during parsing (e.g. invalid hop ip)
            bad_json = tmp_path / f"run_{PILOT_RUN_ID}_routing.json"
            src_json = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_routing.json"
            with open(src_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["hops"][1]["ip"] = ""  # empty ip -> invalid!

            with open(bad_json, "w", encoding="utf-8") as f:
                json.dump(data, f)

            h = compute_file_sha256(bad_json)
            with SessionTest() as session:
                art = session.query(SimulationArtifact).filter_by(file_type="routing_json_p2").first()
                art.file_hash_sha256 = h
                session.commit()

            try:
                ingest_routing_records(PILOT_RUN_ID, dynamic_dir=tmp_path)
            except ValueError:
                pass

            with SessionTest() as session:
                assert session.query(RoutingRecord).count() == 0
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_17_no_pass1_synthetic_record():
    """17. No Pass 1 synthetic record is created."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            with SessionTest() as session:
                p1_records = session.query(RoutingRecord).filter_by(phase="attack_pass1").all()
                assert len(p1_records) == 0
                total_records = session.query(RoutingRecord).all()
                assert len(total_records) == 1
                assert total_records[0].phase == "mitigated_pass2"
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


def test_18_existing_data_invariance():
    """18. Existing B2/B3/B4 data remains unchanged."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)
        from database import session as sess_module
        try:
            with SessionTest() as session:
                c_runs_before = session.query(SimulationRun).count()
                c_metrics_before = session.query(SimulationMetric).count()
                c_energy_before = session.query(NodeEnergyMetric).count()
                c_artifacts_before = session.query(SimulationArtifact).count()
                c_models_before = session.query(ModelRegistry).count()
                c_preds_before = session.query(MLPrediction).count()
                c_trust_before = session.query(TrustEvaluation).count()
                c_prev_before = session.query(PreventionEvent).count()

            ingest_routing_records(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)

            with SessionTest() as session:
                assert session.query(SimulationRun).count() == c_runs_before == 1
                assert session.query(SimulationMetric).count() == c_metrics_before == 106
                assert session.query(NodeEnergyMetric).count() == c_energy_before == 16
                assert session.query(SimulationArtifact).count() == c_artifacts_before == 16
                assert session.query(ModelRegistry).count() == c_models_before == 5
                assert session.query(MLPrediction).count() == c_preds_before == 3576
                assert session.query(TrustEvaluation).count() == c_trust_before == 1160
                assert session.query(PreventionEvent).count() == c_prev_before == 0
                assert session.query(RoutingRecord).count() == 1
        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()


if __name__ == "__main__":
    tests = [
        test_01_valid_pass2_json_mapping,
        test_02_dynamic_simulation_run_resolution,
        test_03_artifact_sha256_verification,
        test_04_invalid_or_missing_json_keys,
        test_05_invalid_hop_sequence,
        test_06_incorrect_hop_count,
        test_07_unknown_malicious_node_metadata,
        test_08_malicious_node_detection,
        test_09_first_ingestion_inserts_exactly_one_record,
        test_10_identical_rerun_inserts_zero_records,
        test_11_existing_primary_key_unchanged_after_rerun,
        test_12_conflicting_existing_record_rejected,
        test_13_missing_simulation_run,
        test_14_missing_source_file,
        test_15_artifact_hash_mismatch,
        test_16_transaction_rollback_on_failure,
        test_17_no_pass1_synthetic_record,
        test_18_existing_data_invariance,
    ]
    passed = 0
    failed = 0
    print(f"Executing {len(tests)} tests for Phase B5.3 Routing Records Ingestion...")
    for t in tests:
        name = t.__name__
        try:
            t()
            passed += 1
            print(f"  [PASS] {name}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\nTest Summary: {passed}/{len(tests)} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
    else:
        print("ALL PHASE B5.3 TESTS PASSED!")
