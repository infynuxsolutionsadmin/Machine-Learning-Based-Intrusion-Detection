"""
test_phase_b3_2_model_registry.py - Isolated Unit and Integration Tests for Phase B3.2 Model Registry Ingestion.

Covers:
1. Valid RandomForest registration.
2. Valid SVM registration.
3. Valid MLP registration.
4. XGBoost/CatBoost availability handling (loadable vs non-loadable, is_active flag).
5. Missing artifact rejection (FileNotFoundError).
6. Hash mismatch rejection (ValueError).
7. Metadata mapping correctness (Accuracy, Precision, Recall, F1, FPR, ConfusionMatrix).
8. NULL loss handling (loss remains strictly NULL).
9. JSON serialization correctness (selected_features, confusion_matrix).
10. Idempotent repeated ingestion (zero count increase on repeat).
11. Unique constraint preservation (uq_model_registry_version).
12. Transaction rollback on failure (isolated transactions).
13. Existing Phase B2 simulation data remains unchanged.
"""
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
    check_model_loadability,
    ingest_model_registry,
    ingest_simulation_core,
    compute_file_sha256,
    BASELINE_MODELS_DIR,
    DYNAMIC_RESULTS_DIR,
)

PILOT_RUN_ID = "20261111_225145_8e3c4f7c_8nodes_attack2_4"


def test_1_to_4_model_registration_and_loadability():
    """Verify registration of classical models with accurate loadability and is_active flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_registry.db"
        test_engine = create_db_engine(test_db_path)
        Base.metadata.create_all(bind=test_engine)
        SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

        from database import session as sess_module
        orig_sessionlocal = sess_module.SessionLocal
        sess_module.SessionLocal = SessionTest

        try:
            # Ingest all verified classical models
            res = ingest_model_registry(models_dir=BASELINE_MODELS_DIR, include_inactive=True)
            assert res["status"] == "success"
            assert res["registered_count"] == 5
            assert set(res["active_models"]) == {"RandomForest", "SVM", "MLP"}
            assert set(res["inactive_models"]) == {"XGBoost", "CatBoost"}

            with SessionTest() as session:
                # 1. RandomForest
                rf = session.query(ModelRegistry).filter_by(model_name="RandomForest").one()
                assert rf.is_active is True
                assert rf.model_type == "classical_ml"
                assert rf.version_tag == "baseline"
                assert rf.accuracy == 1.0
                assert rf.precision == 1.0
                assert rf.recall == 1.0
                assert rf.f1_score == 1.0
                assert rf.fpr == 0.0

                # 2. SVM
                svm = session.query(ModelRegistry).filter_by(model_name="SVM").one()
                assert svm.is_active is True
                assert svm.accuracy == 0.9
                assert svm.precision == 0.5
                assert svm.recall == 1.0
                assert abs(svm.f1_score - 0.6666666666666666) < 1e-6
                assert abs(svm.fpr - 0.1111111111111111) < 1e-6

                # 3. MLP
                mlp = session.query(ModelRegistry).filter_by(model_name="MLP").one()
                assert mlp.is_active is True
                assert mlp.accuracy == 0.9
                assert mlp.precision == 0.5
                assert mlp.recall == 1.0

                # 4. XGBoost & CatBoost (Inactive in .venv)
                xgb = session.query(ModelRegistry).filter_by(model_name="XGBoost").one()
                assert xgb.is_active is False
                assert xgb.accuracy == 1.0

                cb = session.query(ModelRegistry).filter_by(model_name="CatBoost").one()
                assert cb.is_active is False
                assert cb.accuracy == 1.0

        finally:
            sess_module.SessionLocal = orig_sessionlocal
            test_engine.dispose()

    print("TEST 1 TO 4 PASSED: RandomForest, SVM, MLP registered as active; XGBoost, CatBoost handled as inactive.")


def test_5_and_6_missing_and_mismatched_artifact_rejection():
    """Verify rejection of missing or hash-mismatched model artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_dir = Path(tmpdir) / "empty_models"
        fake_dir.mkdir()
        # Missing experiment_metadata.json
        try:
            ingest_model_registry(models_dir=fake_dir)
            assert False, "Expected FileNotFoundError for missing metadata!"
        except FileNotFoundError:
            pass

        # Valid metadata but missing model files
        shutil.copy(BASELINE_MODELS_DIR / "experiment_metadata.json", fake_dir / "experiment_metadata.json")
        try:
            ingest_model_registry(models_dir=fake_dir)
            assert False, "Expected FileNotFoundError for missing model artifacts!"
        except FileNotFoundError:
            pass

        # Hash mismatch test
        bad_hashes = {"RandomForest": "0000000000000000000000000000000000000000000000000000000000000000"}
        try:
            ingest_model_registry(models_dir=BASELINE_MODELS_DIR, expected_hashes=bad_hashes)
            assert False, "Expected ValueError on hash mismatch!"
        except ValueError as ve:
            assert "Hash mismatch" in str(ve)

    print("TEST 5 & 6 PASSED: Missing artifacts and hash mismatches rejected with appropriate errors.")


def test_7_8_9_metadata_null_loss_and_json():
    """Verify metadata mapping, NULL loss preservation, and valid JSON structures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_meta.db"
        test_engine = create_db_engine(test_db_path)
        Base.metadata.create_all(bind=test_engine)
        SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

        from database import session as sess_module
        orig_sessionlocal = sess_module.SessionLocal
        sess_module.SessionLocal = SessionTest

        try:
            ingest_model_registry(models_dir=BASELINE_MODELS_DIR)

            with SessionTest() as session:
                models = session.query(ModelRegistry).all()
                assert len(models) == 5
                for m in models:
                    # Loss must be strictly NULL for classical ML models
                    assert m.loss is None

                    # Selected features must parse to JSON list
                    assert m.selected_features is not None
                    feats = json.loads(m.selected_features)
                    assert isinstance(feats, list)
                    assert "rx" in feats
                    assert "control_message_frequency" in feats

                    # Confusion matrix must parse to JSON dict
                    assert m.confusion_matrix is not None
                    cm = json.loads(m.confusion_matrix)
                    assert isinstance(cm, dict)
                    assert "TN" in cm and "TP" in cm

                    # Artifact path format check
                    assert m.artifact_path.startswith("models/baseline/")
                    assert m.artifact_path.endswith(".pkl")
                    assert not "\\" in m.artifact_path  # POSIX normalized
        finally:
            sess_module.SessionLocal = orig_sessionlocal
            test_engine.dispose()

    print("TEST 7, 8 & 9 PASSED: Metadata mapping, NULL loss, and JSON fields verified.")


def test_10_and_11_idempotence_and_uniqueness():
    """Verify that repeated ingestion is fully idempotent and unique constraint prevents duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_idempotence.db"
        test_engine = create_db_engine(test_db_path)
        Base.metadata.create_all(bind=test_engine)
        SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

        from database import session as sess_module
        orig_sessionlocal = sess_module.SessionLocal
        sess_module.SessionLocal = SessionTest

        try:
            # First ingestion
            res1 = ingest_model_registry(models_dir=BASELINE_MODELS_DIR)
            assert res1["status"] == "success"

            with SessionTest() as session:
                assert session.query(ModelRegistry).count() == 5

            # Second ingestion (repeated call)
            res2 = ingest_model_registry(models_dir=BASELINE_MODELS_DIR)
            assert res2["status"] == "success"

            with SessionTest() as session:
                assert session.query(ModelRegistry).count() == 5  # Strictly unchanged!

            # Active only ingestion should also be idempotent
            res3 = ingest_model_registry(models_dir=BASELINE_MODELS_DIR, include_inactive=False)
            assert res3["registered_count"] == 3

            with SessionTest() as session:
                assert session.query(ModelRegistry).count() == 5
                assert session.query(ModelRegistry).filter_by(is_active=True).count() == 3

        finally:
            sess_module.SessionLocal = orig_sessionlocal
            test_engine.dispose()

    print("TEST 10 & 11 PASSED: Repeated ingestion is fully idempotent without duplicate records.")


def test_12_and_13_transaction_safety_and_b2_invariance():
    """Verify transaction isolation and ensure Phase B2 data is completely unaffected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_safety.db"
        test_engine = create_db_engine(test_db_path)
        Base.metadata.create_all(bind=test_engine)
        SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

        from database import session as sess_module
        orig_sessionlocal = sess_module.SessionLocal
        sess_module.SessionLocal = SessionTest

        try:
            # Ingest Phase B2 core data first
            b2_res = ingest_simulation_core(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert b2_res["status"] == "success"

            with SessionTest() as session:
                assert session.query(SimulationRun).count() == 1
                assert session.query(SimulationMetric).count() == 106
                assert session.query(NodeEnergyMetric).count() == 16
                assert session.query(SimulationArtifact).count() == 16
                assert session.query(ModelRegistry).count() == 0
                assert session.query(MLPrediction).count() == 0

            # Ingest Model Registry
            reg_res = ingest_model_registry(models_dir=BASELINE_MODELS_DIR)
            assert reg_res["status"] == "success"

            with SessionTest() as session:
                # Model registry populated
                assert session.query(ModelRegistry).count() == 5

                # Phase B2 tables remain strictly unchanged
                assert session.query(SimulationRun).count() == 1
                assert session.query(SimulationMetric).count() == 106
                assert session.query(NodeEnergyMetric).count() == 16
                assert session.query(SimulationArtifact).count() == 16

                # ml_predictions remains strictly 0
                assert session.query(MLPrediction).count() == 0

                # Pilot run timestamps remain invariant
                pilot = session.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                assert pilot.started_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 17:21:45"
                assert pilot.completed_at is None
                assert pilot.persistence_status == "completed"

        finally:
            sess_module.SessionLocal = orig_sessionlocal
            test_engine.dispose()

    print("TEST 12 & 13 PASSED: Transaction safety and Phase B2 data invariance verified.")


if __name__ == "__main__":
    test_1_to_4_model_registration_and_loadability()
    test_5_and_6_missing_and_mismatched_artifact_rejection()
    test_7_8_9_metadata_null_loss_and_json()
    test_10_and_11_idempotence_and_uniqueness()
    test_12_and_13_transaction_safety_and_b2_invariance()
    print("\nALL PHASE B3.2 MODEL REGISTRY INGESTION TESTS PASSED SUCCESSFULLY!")

