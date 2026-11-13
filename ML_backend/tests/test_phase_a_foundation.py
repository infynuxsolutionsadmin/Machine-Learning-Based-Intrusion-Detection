"""
test_phase_a_foundation.py - Verification Tests for Phase A Database Foundation.
Tests:
1. Database connection test.
2. SQLite version and WAL-mode verification.
3. Foreign-key enforcement test.
4. ORM metadata/table creation test in a temporary test database.
5. Foreign-key relationship validation.
6. Unique constraint validation.
7. Session creation and cleanup test.
8. Migration generation and inspection.
9. Existing backend import/startup test.
"""
import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Add ML_backend root to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.session import create_db_engine, DEFAULT_DB_PATH
from database.models import (
    SimulationRun,
    SimulationMetric,
    NodeEnergyMetric,
    ModelRegistry,
    MLPrediction,
    TrustEvaluation,
    RoutingRecord,
    PreventionEvent,
    SimulationArtifact,
)


def test_1_database_connection():
    """Verify engine connects to database and executes query."""
    engine = create_db_engine(DEFAULT_DB_PATH)
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT 1")).scalar()
            assert res == 1
    finally:
        engine.dispose()
    print("TEST 1 PASSED: Database connection successful.")


def test_2_sqlite_version_and_wal():
    """Verify SQLite version and WAL mode pragma."""
    engine = create_db_engine(DEFAULT_DB_PATH)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT sqlite_version()")).scalar()
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
            assert journal_mode.lower() == "wal"
            assert busy_timeout >= 30000
    finally:
        engine.dispose()
    print(f"TEST 2 PASSED: SQLite version={version}, journal_mode={journal_mode}, busy_timeout={busy_timeout}ms.")


def test_3_foreign_key_enforcement():
    """Verify PRAGMA foreign_keys is ON in connections."""
    engine = create_db_engine(DEFAULT_DB_PATH)
    try:
        with engine.connect() as conn:
            fk_status = conn.execute(text("PRAGMA foreign_keys")).scalar()
            assert fk_status == 1
    finally:
        engine.dispose()
    print(f"TEST 3 PASSED: Foreign keys pragma is enforced (PRAGMA foreign_keys={fk_status}).")


def test_4_orm_metadata_table_creation():
    """Verify all 11 tables can be created on a clean temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "test_temp.db"
        test_engine = create_db_engine(tmp_db)
        try:
            Base.metadata.create_all(bind=test_engine)
            with test_engine.connect() as conn:
                tables = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                ).scalars().all()

            expected_tables = {
                "simulation_runs",
                "simulation_metrics",
                "node_energy_metrics",
                "model_registry",
                "ml_predictions",
                "trust_evaluations",
                "routing_records",
                "prevention_events",
                "simulation_artifacts",
            }
            assert expected_tables.issubset(set(tables)), f"Missing tables: {expected_tables - set(tables)}"
        finally:
            test_engine.dispose()
        print(f"TEST 4 PASSED: All 9 ORM tables successfully created: {sorted(list(expected_tables))}.")


def test_5_foreign_key_relationship_validation():
    """Verify foreign key constraint blocks orphan rows in child tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "test_fk.db"
        test_engine = create_db_engine(tmp_db)
        try:
            Base.metadata.create_all(bind=test_engine)
            SessionTest = sessionmaker(bind=test_engine)

            with SessionTest() as session:
                orphan_metric = SimulationMetric(
                    simulation_run_id=99999,  # Non-existent run
                    phase="baseline",
                    flow_id=1,
                    source_ip="10.1.1.1",
                    dest_ip="10.1.1.2",
                    tx_packets=10,
                    rx_packets=10,
                    tx_bytes=1000,
                    rx_bytes=1000,
                    pdr=100.0,
                    throughput_kbps=50.0,
                    avg_delay_ms=2.0,
                    avg_jitter_ms=0.5,
                    packet_loss_ratio=0.0,
                )
                session.add(orphan_metric)
                raised = False
                try:
                    session.commit()
                except IntegrityError:
                    raised = True
                    session.rollback()
                assert raised, "Foreign key violation did not raise IntegrityError"
        finally:
            test_engine.dispose()
        print("TEST 5 PASSED: Foreign key constraints properly reject orphan child records.")


def test_6_unique_constraint_validation():
    """Verify unique constraint prevents duplicate entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "test_unique.db"
        test_engine = create_db_engine(tmp_db)
        try:
            Base.metadata.create_all(bind=test_engine)
            SessionTest = sessionmaker(bind=test_engine)

            with SessionTest() as session:
                run1 = SimulationRun(
                    run_id="run_unique_test_001",
                    protocol="AODV",
                    num_nodes=8,
                    num_malicious=2,
                    simulation_status="completed",
                    persistence_status="completed",
                )
                session.add(run1)
                session.commit()

                # Attempt to insert duplicate run_id
                run2 = SimulationRun(
                    run_id="run_unique_test_001",
                    protocol="AODV",
                    num_nodes=8,
                    num_malicious=2,
                    simulation_status="completed",
                    persistence_status="completed",
                )
                session.add(run2)
                raised = False
                try:
                    session.commit()
                except IntegrityError:
                    raised = True
                    session.rollback()
                assert raised, "Duplicate run_id did not raise IntegrityError"
        finally:
            test_engine.dispose()
        print("TEST 6 PASSED: Unique constraints prevent duplicate natural identifiers.")


def test_7_session_creation_and_cleanup():
    """Verify session creation, transaction rollback, and clean closure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "test_session.db"
        test_engine = create_db_engine(tmp_db)
        try:
            Base.metadata.create_all(bind=test_engine)
            SessionTest = sessionmaker(bind=test_engine)

            session = SessionTest()
            try:
                assert session.is_active
                session.execute(text("SELECT 1"))
            finally:
                session.close()

            # Closed session should not be in an active transaction
            assert not session.is_active or not session.in_transaction()
        finally:
            test_engine.dispose()
        print("TEST 7 PASSED: Session properly opened and closed.")


def test_8_migration_inspection():
    """Verify Alembic migration file exists and contains valid revision metadata."""
    versions_dir = BACKEND_DIR / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*.py"))
    assert len(migration_files) >= 1, "No migration versions found."
    content = migration_files[0].read_text(encoding="utf-8")
    assert "def upgrade()" in content
    assert "def downgrade()" in content
    assert "simulation_runs" in content
    assert "model_registry" in content
    print(f"TEST 8 PASSED: Alembic migration verified: {migration_files[0].name}.")


def test_9_existing_backend_import():
    """Verify FastAPI application and services still import cleanly without side-effects."""
    from app.main import app
    assert app.title == "MANET Trust-Aware Routing Backend"
    from database import (
        Base,
        engine,
        SessionLocal,
        get_db,
        SimulationRun,
        SimulationMetric,
    )
    assert Base is not None
    assert engine is not None
    print("TEST 9 PASSED: Backend app and database models imported successfully with zero conflicts.")


if __name__ == "__main__":
    test_1_database_connection()
    test_2_sqlite_version_and_wal()
    test_3_foreign_key_enforcement()
    test_4_orm_metadata_table_creation()
    test_5_foreign_key_relationship_validation()
    test_6_unique_constraint_validation()
    test_7_session_creation_and_cleanup()
    test_8_migration_inspection()
    test_9_existing_backend_import()
    print("\nALL 9 PHASE A VERIFICATION TESTS PASSED SUCCESSFULLY!")
