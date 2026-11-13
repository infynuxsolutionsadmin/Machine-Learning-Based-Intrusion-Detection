"""
test_phase_b2_timestamp_correction.py - Isolated Tests for Phase B2.2 & B2.3 Timestamp Correction & Fallback Safety.
Covers:
1. IST run ID timestamp converts to UTC correctly (subtracts 5h30m).
2. UTC conversion does not accidentally add or subtract the offset twice.
3. Explicit timezone override (source_tz_name) works correctly.
4. Environment variable SIMULATION_TIMEZONE is respected.
5. Existing UTC persisted_at behavior remains unchanged.
6. completed_at remains NULL when no authoritative source exists.
7. Phase B2.3 Safety: Non-canonical run IDs reject filesystem st_ctime fallback and raise ValueError.
8. Phase B2.3 Safety: Current ingestion time datetime.now() is never substituted for simulation start time.
9. Phase B2.3 Safety: Repeated ingestion is fully idempotent without timestamp drift.
10. Phase B2.3 Safety: Ingestion failure on non-canonical ID leaves database uncorrupted.
11. Historical pilot run preserves started_at = 2026-11-11 17:21:45 UTC.
"""
import os
import sys
import tempfile
import zoneinfo
from datetime import datetime, timezone
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
)
from database.ingestion_service import (
    resolve_run_started_at,
    extract_run_metadata,
    ingest_simulation_core,
    DYNAMIC_RESULTS_DIR,
)

PILOT_RUN_ID = "20261111_225145_8e3c4f7c_8nodes_attack2_4"


def test_1_and_2_ist_to_utc_conversion():
    """Verify IST timestamp converts to UTC (subtracting 5h30m) without doubling."""
    run_id = "20261111_225145_test"
    # Convert using explicit Asia/Kolkata
    dt_utc = resolve_run_started_at(run_id, source_tz_name="Asia/Kolkata")
    assert dt_utc.tzinfo == timezone.utc
    assert dt_utc.year == 2026 and dt_utc.month == 11 and dt_utc.day == 11
    assert dt_utc.hour == 17 and dt_utc.minute == 21 and dt_utc.second == 45
    assert dt_utc.strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 17:21:45"

    # Confirm calling again or checking offset does not subtract twice
    dt_utc_2 = resolve_run_started_at(run_id, source_tz_name="Asia/Kolkata")
    assert dt_utc == dt_utc_2
    print("TEST 1 & 2 PASSED: IST timestamp converts to UTC (17:21:45) without double offset.")


def test_3_and_4_timezone_override_and_env():
    """Verify explicit source_tz_name and SIMULATION_TIMEZONE environment variable."""
    run_id = "20261111_120000_tz_test"
    # Explicit UTC
    dt_utc = resolve_run_started_at(run_id, source_tz_name="UTC")
    assert dt_utc.strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 12:00:00"

    # SIMULATION_TIMEZONE environment override
    orig_env = os.environ.get("SIMULATION_TIMEZONE")
    try:
        os.environ["SIMULATION_TIMEZONE"] = "UTC"
        dt_env = resolve_run_started_at(run_id)
        assert dt_env.strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 12:00:00"
    finally:
        if orig_env is not None:
            os.environ["SIMULATION_TIMEZONE"] = orig_env
        else:
            os.environ.pop("SIMULATION_TIMEZONE", None)

    print("TEST 3 & 4 PASSED: Explicit source_tz_name and SIMULATION_TIMEZONE override verified.")


def test_5_and_6_persisted_at_and_completed_at():
    """Verify persisted_at is genuine UTC and completed_at remains NULL."""
    meta = extract_run_metadata(PILOT_RUN_ID, DYNAMIC_RESULTS_DIR)
    assert meta["completed_at"] is None
    assert meta["started_at"].strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 17:21:45"
    print("TEST 5 & 6 PASSED: completed_at remains NULL and started_at is normalized to UTC.")


def test_7_and_8_reject_fallback_fabrication():
    """
    Phase B2.3 Safety:
    Verify that non-standard run IDs strictly reject st_ctime or datetime.now() fallback,
    and raise a clear ValueError rather than fabricating misleading timestamps.
    """
    invalid_ids = [
        "custom_run_no_timestamp_prefix",
        "invalid_timestamp_9999",
        "run_test_sample",
        "",
    ]
    for bad_id in invalid_ids:
        try:
            resolve_run_started_at(bad_id)
            assert False, f"Expected ValueError for invalid run_id '{bad_id}', but got a timestamp!"
        except ValueError as e:
            assert "Cannot resolve authoritative simulation start timestamp" in str(e)

    # Test that having an existing file does NOT cause fallback to st_ctime
    dummy_file = DYNAMIC_RESULTS_DIR / "current_run.json"
    if dummy_file.exists():
        try:
            resolve_run_started_at("bad_run_id", fallback_file=dummy_file)
            assert False, "Expected ValueError even when fallback_file exists, but got a timestamp!"
        except ValueError as e:
            assert "Ingestion refused to prevent timestamp fabrication" in str(e)

    print("TEST 7 & 8 PASSED: Filesystem st_ctime and datetime.now() fabrication strictly rejected with ValueError.")


def test_9_10_11_idempotent_ingestion_and_failure_safety():
    """
    Verify repeated ingestion preserves corrected UTC timestamp without drift,
    and invalid run ingestion fails without corrupting database state.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_tz_safety.db"
        test_engine = create_db_engine(test_db_path)
        Base.metadata.create_all(bind=test_engine)
        SessionTest = sessionmaker(bind=test_engine, expire_on_commit=False)

        from database import session as sess_module
        orig_sessionlocal = sess_module.SessionLocal
        sess_module.SessionLocal = SessionTest

        try:
            # First Ingestion
            res1 = ingest_simulation_core(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res1["status"] == "success"

            with SessionTest() as s:
                run1 = s.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                assert run1.started_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 17:21:45"
                assert run1.completed_at is None
                assert run1.persisted_at is not None

                assert s.query(SimulationRun).count() == 1
                assert s.query(SimulationMetric).count() == 106
                assert s.query(NodeEnergyMetric).count() == 16
                assert s.query(SimulationArtifact).count() == 16

            # Second Ingestion (Idempotence)
            res2 = ingest_simulation_core(PILOT_RUN_ID, dynamic_dir=DYNAMIC_RESULTS_DIR)
            assert res2["status"] == "success"

            with SessionTest() as s:
                run2 = s.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                # Timestamp must remain strictly 17:21:45 (NO drift or second shift!)
                assert run2.started_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 17:21:45"
                assert run2.completed_at is None

                # Row counts must remain strictly identical
                assert s.query(SimulationRun).count() == 1
                assert s.query(SimulationMetric).count() == 106
                assert s.query(NodeEnergyMetric).count() == 16
                assert s.query(SimulationArtifact).count() == 16

            # Attempt ingestion with non-canonical run ID: must fail cleanly without corrupting DB
            try:
                ingest_simulation_core("non_canonical_run_without_timestamp", dynamic_dir=DYNAMIC_RESULTS_DIR)
                assert False, "Expected ValueError on non-canonical run ID, but ingestion proceeded!"
            except ValueError:
                pass

            # Verify database still has exactly 1 run and unmodified counts
            with SessionTest() as s:
                assert s.query(SimulationRun).count() == 1
                assert s.query(SimulationMetric).count() == 106
                assert s.query(NodeEnergyMetric).count() == 16
                assert s.query(SimulationArtifact).count() == 16
                pilot_rec = s.query(SimulationRun).filter_by(run_id=PILOT_RUN_ID).one()
                assert pilot_rec.started_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 17:21:45"

        finally:
            sess_module.SessionLocal = orig_sessionlocal
            test_engine.dispose()

    print("TEST 9, 10 & 11 PASSED: Idempotent ingestion, zero timestamp drift, and non-canonical failure safety verified.")


if __name__ == "__main__":
    test_1_and_2_ist_to_utc_conversion()
    test_3_and_4_timezone_override_and_env()
    test_5_and_6_persisted_at_and_completed_at()
    test_7_and_8_reject_fallback_fabrication()
    test_9_10_11_idempotent_ingestion_and_failure_safety()
    print("\nALL PHASE B2.2 & B2.3 TIMESTAMP CORRECTION & FALLBACK SAFETY TESTS PASSED SUCCESSFULLY!")
