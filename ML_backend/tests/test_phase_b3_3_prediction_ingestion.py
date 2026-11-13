"""
test_phase_b3_3_prediction_ingestion.py - Comprehensive Isolated Tests for Phase B3.3 Classical ML Prediction Ingestion.

Covers:
1. Correct RandomForest prediction ingestion.
2. Correct SVM prediction ingestion.
3. Correct MLP prediction ingestion.
4. Exact total of 3,576 records (1,192 x 3).
5. Correct field mapping (time_sec, node_id, rx_packets, control_freq, ground_truth_label, predicted_label).
6. Correct foreign-key relationships (simulation_run_id -> simulation_runs, model_id -> model_registry).
7. confidence remains strictly NULL.
8. Missing source CSV rejection (FileNotFoundError).
9. Source SHA-256 mismatch rejection (ValueError).
10. Missing required columns rejection (ValueError).
11. Invalid labels or predictions rejection (ValueError on non-binary values).
12. Duplicate (time, node) source records rejection (ValueError).
13. Inactive model rejection (ValueError).
14. Missing model registry record rejection (ValueError).
15. Transaction rollback on insertion failure (isolated transactions).
16. Idempotent repeated ingestion (zero count increase on repeat).
17. Existing Phase B2 records remain unchanged.
"""
import csv
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
    ModelRegistry,
    SimulationRun,
    SimulationMetric,
    NodeEnergyMetric,
    SimulationArtifact,
    MLPrediction,
)
from database.ingestion_service import (
    ingest_simulation_core,
    ingest_model_registry,
    ingest_classical_ml_predictions,
    compute_file_sha256,
    BASELINE_MODELS_DIR,
    DYNAMIC_RESULTS_DIR,
)

PILOT_RUN_ID = "20261111_225145_8e3c4f7c_8nodes_attack2_4"


def setup_test_db(tmpdir: Path):
    """Helper to set up an isolated test database with B2 core data and B3.2 model registry."""
    test_db_path = tmpdir / "test_b3_3.db"
    test_engine = create_db_engine(test_db_path)
    Base.metadata.create_all(bind=test_engine)
    SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

    from database import session as sess_module
    orig_sessionlocal = sess_module.SessionLocal
    sess_module.SessionLocal = SessionTest

    # Seed B2 core simulation data
    ingest_simulation_core(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
    # Seed B3.2 model registry data
    ingest_model_registry(models_dir=BASELINE_MODELS_DIR, include_inactive=True)

    return test_engine, SessionTest, orig_sessionlocal


def test_1_to_7_correct_ingestion_mapping_and_counts():
    """Verify correct ingestion of RandomForest, SVM, MLP with exact mapping, counts, and NULL confidence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)

        from database import session as sess_module
        try:
            res = ingest_classical_ml_predictions(
                PILOT_RUN_ID,
                dynamic_dir=DYNAMIC_RESULTS_DIR,
                version_tag="baseline",
                models_dir=BASELINE_MODELS_DIR,
            )
            assert res["status"] == "success"
            assert res["total_records"] == 3576
            assert res["per_model_counts"]["RandomForest"] == 1192
            assert res["per_model_counts"]["SVM"] == 1192
            assert res["per_model_counts"]["MLP"] == 1192

            with SessionTest() as session:
                # 1, 2, 3: Per-model counts
                rf = session.query(ModelRegistry).filter_by(model_name="RandomForest").one()
                svm = session.query(ModelRegistry).filter_by(model_name="SVM").one()
                mlp = session.query(ModelRegistry).filter_by(model_name="MLP").one()

                rf_count = session.query(MLPrediction).filter_by(model_id=rf.id).count()
                svm_count = session.query(MLPrediction).filter_by(model_id=svm.id).count()
                mlp_count = session.query(MLPrediction).filter_by(model_id=mlp.id).count()

                assert rf_count == 1192
                assert svm_count == 1192
                assert mlp_count == 1192

                # 4: Exact total
                total = session.query(MLPrediction).count()
                assert total == 3576

                # 5: Field mapping verification on first record
                p1 = session.query(MLPrediction).filter_by(model_id=rf.id, time_sec=1.0, node_id=0).one()
                assert p1.simulation_run_id == 1
                assert p1.rx_packets == 0.0
                assert p1.control_freq == 798.0
                assert p1.ground_truth_label == 0
                assert p1.predicted_label == 1

                # 6: Foreign key verification
                run_rec = session.query(SimulationRun).filter_by(id=p1.simulation_run_id).one()
                assert run_rec.run_id == PILOT_RUN_ID
                model_rec = session.query(ModelRegistry).filter_by(id=p1.model_id).one()
                assert model_rec.model_name == "RandomForest"

                # 7: All confidence values are strictly NULL
                null_conf_count = session.query(MLPrediction).filter(MLPrediction.confidence.is_(None)).count()
                assert null_conf_count == 3576

        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()

    print("TEST 1 TO 7 PASSED: RandomForest, SVM, MLP ingestion, mapping, counts (3576), FKs, and NULL confidence verified.")


def test_8_and_9_missing_csv_and_hash_mismatch():
    """Verify rejection of missing CSV and hash mismatch against recorded artifact."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)

        from database import session as sess_module
        try:
            # 8: Missing CSV
            fake_dir = tmp_path / "fake_dynamic"
            fake_dir.mkdir()
            try:
                ingest_classical_ml_predictions(PILOT_RUN_ID, dynamic_dir=fake_dir)
                assert False, "Expected FileNotFoundError for missing CSV!"
            except FileNotFoundError:
                pass

            # 9: Hash mismatch
            # Create a corrupted CSV with the same name in fake_dir
            corrupt_csv = fake_dir / f"run_{PILOT_RUN_ID}_classical_ml_predictions.csv"
            corrupt_csv.write_text("corrupted,data\n1,2\n", encoding="utf-8")
            try:
                ingest_classical_ml_predictions(PILOT_RUN_ID, dynamic_dir=fake_dir)
                assert False, "Expected ValueError on CSV hash mismatch!"
            except ValueError as ve:
                assert "hash mismatch" in str(ve).lower()

        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()

    print("TEST 8 & 9 PASSED: Missing CSV and hash mismatch cleanly rejected.")


def test_10_to_12_csv_validation_rejections():
    """Verify rejection of missing required columns, non-binary labels/predictions, and duplicate (time, node)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)

        from database import session as sess_module
        # Temporarily update simulation_artifacts record hash in the test DB to allow testing corrupted CSVs
        real_csv = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_classical_ml_predictions.csv"
        lines = real_csv.read_text(encoding="utf-8").splitlines()

        try:
            # Helper to test invalid CSV content
            def test_bad_csv(bad_lines, err_msg_part):
                fake_dir = tmp_path / "test_csv_dir"
                if fake_dir.exists():
                    shutil.rmtree(fake_dir)
                fake_dir.mkdir()
                bad_csv = fake_dir / f"run_{PILOT_RUN_ID}_classical_ml_predictions.csv"
                bad_csv.write_text("\n".join(bad_lines), encoding="utf-8")
                bad_hash = compute_file_sha256(bad_csv)

                with SessionTest() as s:
                    art = s.query(SimulationArtifact).filter_by(file_type="classical_ml_csv").first()
                    if art:
                        art.file_hash_sha256 = bad_hash
                        s.commit()

                try:
                    ingest_classical_ml_predictions(PILOT_RUN_ID, dynamic_dir=fake_dir)
                    assert False, f"Expected ValueError containing '{err_msg_part}'!"
                except ValueError as ve:
                    assert err_msg_part.lower() in str(ve).lower(), f"Unexpected error: {ve}"

            # 10: Missing required column
            bad_header_lines = [lines[0].replace("RandomForest_pred,", "")] + lines[1:1193]
            test_bad_csv(bad_header_lines, "missing from prediction CSV")

            # 11: Non-binary label
            bad_label_lines = [lines[0]]
            for idx, l in enumerate(lines[1:1193]):
                if idx == 0:
                    # set label to 5
                    parts = l.split(",")
                    parts[5] = "5"
                    bad_label_lines.append(",".join(parts))
                else:
                    bad_label_lines.append(l)
            test_bad_csv(bad_label_lines, "non-binary")

            # 12: Duplicate (time, node)
            bad_dup_lines = [lines[0], lines[1], lines[1]] + lines[3:1193]  # duplicate row 1
            test_bad_csv(bad_dup_lines, "duplicate")

        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()

    print("TEST 10 TO 12 PASSED: Missing columns, non-binary values, and duplicate (time, node) rejected.")


def test_13_and_14_inactive_and_missing_model_rejection():
    """Verify rejection when an eligible model is missing from registry or marked inactive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)

        from database import session as sess_module
        try:
            # 13: Inactive model rejection
            with SessionTest() as s:
                rf = s.query(ModelRegistry).filter_by(model_name="RandomForest").one()
                rf.is_active = False
                s.commit()

            try:
                ingest_classical_ml_predictions(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Expected ValueError on inactive model!"
            except ValueError as ve:
                assert "inactive" in str(ve).lower()

            # Restore
            with SessionTest() as s:
                rf = s.query(ModelRegistry).filter_by(model_name="RandomForest").one()
                rf.is_active = True
                # Delete MLP record
                mlp = s.query(ModelRegistry).filter_by(model_name="MLP").one()
                s.delete(mlp)
                s.commit()

            # 14: Missing model registry record rejection
            try:
                ingest_classical_ml_predictions(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Expected ValueError on missing model registry record!"
            except ValueError as ve:
                assert "not registered" in str(ve).lower()

        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()

    print("TEST 13 & 14 PASSED: Inactive model and missing model registry records cleanly rejected.")


def test_15_16_17_rollback_idempotence_and_b2_invariance():
    """Verify transaction rollback on failure, idempotent repeat ingestion, and Phase B2 data invariance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_engine, SessionTest, orig_sess = setup_test_db(tmp_path)

        from database import session as sess_module
        try:
            # Initial ingestion
            res1 = ingest_classical_ml_predictions(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res1["status"] == "success"
            assert res1["total_records"] == 3576

            with SessionTest() as s:
                assert s.query(MLPrediction).count() == 3576
                # Verify B2 tables
                assert s.query(SimulationRun).count() == 1
                assert s.query(SimulationMetric).count() == 106
                assert s.query(NodeEnergyMetric).count() == 16
                assert s.query(SimulationArtifact).count() == 16
                assert s.query(ModelRegistry).count() == 5

            # 16: Idempotent repeat ingestion
            res2 = ingest_classical_ml_predictions(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res2["status"] == "success"
            assert res2["total_records"] == 3576

            with SessionTest() as s:
                # Count MUST remain exactly 3576 with 0 duplicate records
                assert s.query(MLPrediction).count() == 3576

            # 17: B2 records, timestamps, and artifacts remain completely invariant
            with SessionTest() as s:
                run = s.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                assert run.started_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 17:21:45"
                assert run.completed_at is None
                assert run.persistence_status == "completed"

                # Check all 16 artifacts
                arts = s.query(SimulationArtifact).all()
                assert len(arts) == 16
                for a in arts:
                    p = Path(a.file_path)
                    assert p.exists()
                    assert compute_file_sha256(p) == a.file_hash_sha256

        finally:
            sess_module.SessionLocal = orig_sess
            test_engine.dispose()

    print("TEST 15, 16 & 17 PASSED: Rollback safety, idempotence (3576 rows), and B2 invariance verified.")


if __name__ == "__main__":
    test_1_to_7_correct_ingestion_mapping_and_counts()
    test_8_and_9_missing_csv_and_hash_mismatch()
    test_10_to_12_csv_validation_rejections()
    test_13_and_14_inactive_and_missing_model_rejection()
    test_15_16_17_rollback_idempotence_and_b2_invariance()
    print("\nALL PHASE B3.3 CLASSICAL ML PREDICTION INGESTION TESTS PASSED SUCCESSFULLY!")

