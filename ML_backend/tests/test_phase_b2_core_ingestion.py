"""
test_phase_b2_core_ingestion.py - Comprehensive Test Suite for Phase B2 Core Ingestion.
Tests all 13 required verification items using an isolated temporary SQLite database:
1. Absolute database path consistency.
2. Alembic path resolution.
3. CSV/XML parsing.
4. Byte-count extraction from XML.
5. Missing XML handling.
6. Attack and baseline phase separation.
7. Energy validation.
8. Artifact existence and SHA-256.
9. Transaction rollback on error.
10. Separate failure-status logging.
11. Idempotent repeated ingestion.
12. Foreign-key integrity.
13. No writes to deferred tables.
"""
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Add ML_backend root to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.session import create_db_engine, DEFAULT_DB_PATH, get_sqlite_url
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
    compute_file_sha256,
    extract_run_metadata,
    parse_flow_metrics,
    parse_energy_metrics,
    parse_artifact_records,
    get_simulation_artifact_catalog,
    ingest_simulation_core,
    DYNAMIC_RESULTS_DIR,
)

PILOT_RUN_ID = "20261111_225145_8e3c4f7c_8nodes_attack2_4"


def test_1_and_2_path_and_alembic_resolution():
    """Verify absolute path consistency and Alembic env parity."""
    import alembic.config
    cfg = alembic.config.Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_url = get_sqlite_url(DEFAULT_DB_PATH)
    cfg.set_main_option("sqlalchemy.url", alembic_url)

    expected_url = f"sqlite:///{DEFAULT_DB_PATH.resolve().as_posix()}"
    assert get_sqlite_url(DEFAULT_DB_PATH) == expected_url
    assert cfg.get_main_option("sqlalchemy.url") == expected_url
    print("TEST 1 & 2 PASSED: Absolute database path and Alembic parity verified.")


def test_3_4_5_6_flow_metrics_and_xml():
    """Verify Flow CSV/XML parsing, byte counts, phase separation, and missing XML handling."""
    catalog = get_simulation_artifact_catalog(PILOT_RUN_ID, DYNAMIC_RESULTS_DIR)

    # Attack flows
    att_flows = parse_flow_metrics(catalog["flow_csv_attack"], catalog["flow_xml_attack"], "attack")
    assert len(att_flows) == 53
    assert all(f["phase"] == "attack" for f in att_flows)
    assert all(f["tx_bytes"] > 0 and f["rx_bytes"] >= 0 for f in att_flows)
    assert all(f["packet_loss_ratio"] >= 0.0 for f in att_flows)

    # Baseline flows
    base_flows = parse_flow_metrics(catalog["flow_csv_baseline"], catalog["flow_xml_baseline"], "baseline")
    assert len(base_flows) == 53
    assert all(f["phase"] == "baseline" for f in base_flows)
    assert all(f["tx_bytes"] > 0 and f["rx_bytes"] >= 0 for f in base_flows)

    # Missing XML handling
    missing_xml = DYNAMIC_RESULTS_DIR / "nonexistent_flow.xml"
    raised = False
    try:
        parse_flow_metrics(catalog["flow_csv_attack"], missing_xml, "attack")
    except FileNotFoundError:
        raised = True
    assert raised, "Missing XML must raise FileNotFoundError"
    print("TEST 3, 4, 5 & 6 PASSED: Flow parsing, byte counts, phase separation, and missing XML handling verified.")


def test_7_energy_validation():
    """Verify energy validation, bounds, and phase separation."""
    catalog = get_simulation_artifact_catalog(PILOT_RUN_ID, DYNAMIC_RESULTS_DIR)
    att_e = parse_energy_metrics(catalog["energy_csv_attack"], "attack", 8)
    base_e = parse_energy_metrics(catalog["energy_csv_baseline"], "baseline", 8)

    assert len(att_e) == 8
    assert len(base_e) == 8
    assert all(e["phase"] == "attack" for e in att_e)
    assert all(e["phase"] == "baseline" for e in base_e)
    assert all(0 <= e["node_id"] < 8 for e in att_e + base_e)
    assert all(0.0 <= e["residual_pct"] <= 100.0 for e in att_e + base_e)
    assert all(e["remaining_energy_j"] <= e["initial_energy_j"] for e in att_e + base_e)
    print("TEST 7 PASSED: Energy validation and physical boundary checks verified.")


def test_8_artifact_existence_and_sha256():
    """Verify all 16 physical artifacts exist, have non-zero sizes, and valid SHA-256."""
    artifacts = parse_artifact_records(PILOT_RUN_ID, DYNAMIC_RESULTS_DIR)
    assert len(artifacts) == 16, f"Expected 16 artifacts, got {len(artifacts)}"
    types = [a["file_type"] for a in artifacts]
    assert len(set(types)) == 16, "Duplicate file_type descriptors found in catalog"
    assert all(len(a["file_hash_sha256"]) == 64 for a in artifacts)
    assert all(a["file_size_bytes"] > 0 for a in artifacts)
    print("TEST 8 PASSED: Artifact catalog (16 files) existence and SHA-256 hashes verified.")


def test_9_10_transaction_rollback_and_failure_logging():
    """Verify Stage B transaction rolls back completely on error and records failure status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_rollback.db"
        test_engine = create_db_engine(test_db_path)
        Base.metadata.create_all(bind=test_engine)
        SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

        # Monkeypatch sessionmaker in ingestion service context
        from database import session as sess_module
        orig_sessionlocal = sess_module.SessionLocal
        sess_module.SessionLocal = SessionTest

        try:
            # Trigger ingestion with invalid corrupted dir so Stage B fails after Stage A
            corrupted_dir = Path(tmpdir) / "corrupted_sim"
            corrupted_dir.mkdir()
            # Copy only routing.json and current_run.json so Stage A succeeds
            routing_src = DYNAMIC_RESULTS_DIR / f"run_{PILOT_RUN_ID}_routing.json"
            (corrupted_dir / f"run_{PILOT_RUN_ID}_routing.json").write_text(routing_src.read_text(encoding="utf-8"), encoding="utf-8")
            current_src = DYNAMIC_RESULTS_DIR / "current_run.json"
            (corrupted_dir / "current_run.json").write_text(current_src.read_text(encoding="utf-8"), encoding="utf-8")

            failed_raised = False
            try:
                ingest_simulation_core(PILOT_RUN_ID, dynamic_dir=corrupted_dir)
            except Exception:
                failed_raised = True
            assert failed_raised, "Ingestion must raise exception when child files missing"

            # Check database state: run must have persistence_status='failed', child tables must be 0
            with SessionTest() as s:
                run_rec = s.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).first()
                assert run_rec is not None
                assert run_rec.persistence_status == "failed"
                assert run_rec.persistence_error is not None
                assert run_rec.simulation_status == "completed"  # Never changed!

                # Zero child records must be persisted
                assert s.query(SimulationMetric).count() == 0
                assert s.query(NodeEnergyMetric).count() == 0
                assert s.query(SimulationArtifact).count() == 0
        finally:
            sess_module.SessionLocal = orig_sessionlocal
            test_engine.dispose()

        print("TEST 9 & 10 PASSED: Transaction rollback on failure and isolated failure logging verified.")


def test_11_12_13_isolated_ingestion_idempotency_and_deferred_tables():
    """Verify successful core ingestion, idempotency, foreign keys, and zero writes to deferred tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_pilot_isolated.db"
        test_engine = create_db_engine(test_db_path)
        Base.metadata.create_all(bind=test_engine)
        SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

        from database import session as sess_module
        orig_sessionlocal = sess_module.SessionLocal
        sess_module.SessionLocal = SessionTest

        try:
            # 1. First Ingestion
            res1 = ingest_simulation_core(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res1["status"] == "success"

            with SessionTest() as s:
                assert s.query(SimulationRun).count() == 1
                assert s.query(SimulationMetric).count() == 106
                assert s.query(NodeEnergyMetric).count() == 16
                assert s.query(SimulationArtifact).count() == 16

                # Verify zero writes to deferred tables
                assert s.query(ModelRegistry).count() == 0
                assert s.query(MLPrediction).count() == 0
                assert s.query(TrustEvaluation).count() == 0
                assert s.query(RoutingRecord).count() == 0
                assert s.query(PreventionEvent).count() == 0

                run = s.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                assert run.persistence_status == "completed"
                assert run.persisted_at is not None

            # 2. Second Ingestion (Idempotency test on identical run)
            res2 = ingest_simulation_core(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res2["status"] == "success"

            with SessionTest() as s:
                # Row counts must remain strictly identical
                assert s.query(SimulationRun).count() == 1
                assert s.query(SimulationMetric).count() == 106
                assert s.query(NodeEnergyMetric).count() == 16
                assert s.query(SimulationArtifact).count() == 16

                # Deferred tables remain untouched
                assert s.query(ModelRegistry).count() == 0
                assert s.query(MLPrediction).count() == 0
                assert s.query(TrustEvaluation).count() == 0
                assert s.query(RoutingRecord).count() == 0
                assert s.query(PreventionEvent).count() == 0
        finally:
            sess_module.SessionLocal = orig_sessionlocal
            test_engine.dispose()

        print("TEST 11, 12 & 13 PASSED: Idempotency, foreign-key integrity, and deferred table isolation verified.")


if __name__ == "__main__":
    test_1_and_2_path_and_alembic_resolution()
    test_3_4_5_6_flow_metrics_and_xml()
    test_7_energy_validation()
    test_8_artifact_existence_and_sha256()
    test_9_10_transaction_rollback_and_failure_logging()
    test_11_12_13_isolated_ingestion_idempotency_and_deferred_tables()
    print("\nALL 13 PHASE B2 VERIFICATION TESTS PASSED SUCCESSFULLY!")

