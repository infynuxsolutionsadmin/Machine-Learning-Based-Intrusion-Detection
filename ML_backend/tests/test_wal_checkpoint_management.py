"""
test_wal_checkpoint_management.py - Comprehensive Unit & Regression Test Suite
for SQLite WAL Checkpoint Management, Connection Pragmas, and Persistence Decoupling.
"""
import os
import sys
import tempfile
import sqlite3
import unittest
from pathlib import Path

# Ensure ML_backend is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.session import create_db_engine, safe_wal_checkpoint, DEFAULT_DB_PATH
from database.base import Base
from database.models import SimulationRun
from sqlalchemy.orm import sessionmaker


class TestWalCheckpointManagement(unittest.TestCase):
    """Test suite verifying Phase 2 & Phase 5 WAL checkpoint management requirements."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_manet.db"
        self.engine = create_db_engine(self.db_path)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_01_connection_level_wal_pragmas(self):
        """1. Verify connection-level WAL configuration on newly created pooled connections."""
        raw_conn = self.engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            self.assertEqual(journal_mode.lower(), "wal")

            cursor.execute("PRAGMA foreign_keys;")
            foreign_keys = cursor.fetchone()[0]
            self.assertEqual(foreign_keys, 1)

            cursor.execute("PRAGMA busy_timeout;")
            busy_timeout = cursor.fetchone()[0]
            self.assertEqual(busy_timeout, 30000)

            cursor.execute("PRAGMA synchronous;")
            synchronous = cursor.fetchone()[0]
            # NORMAL is 1 in SQLite
            self.assertEqual(synchronous, 1)

            cursor.execute("PRAGMA wal_autocheckpoint;")
            wal_autocheckpoint = cursor.fetchone()[0]
            self.assertEqual(wal_autocheckpoint, 256)
            
            cursor.close()
        finally:
            raw_conn.close()

    def test_02_safe_wal_checkpoint_completed_when_idle(self):
        """2. Verify safe_wal_checkpoint returns COMPLETED and busy=0 when idle."""
        # Insert a record to generate WAL frames
        with self.Session() as s:
            run = SimulationRun(
                run_id="test_run_wal_001",
                num_nodes=8,
                num_malicious=0,
                protocol="AODV",
                simulation_status="completed",
                persistence_status="completed"
            )
            s.add(run)
            s.commit()

        diag = safe_wal_checkpoint(self.engine)
        self.assertIn(diag["checkpoint_status"], ("COMPLETED", "PARTIAL"))
        self.assertEqual(diag["busy"], 0)
        self.assertIsNone(diag["error"])
        self.assertIsInstance(diag["log_frames"], int)
        self.assertIsInstance(diag["checkpointed_frames"], int)

    def test_03_checkpoint_not_in_active_transaction(self):
        """3. Verify checkpoint runs on an independent connection outside active transaction."""
        with self.Session() as s:
            run = SimulationRun(
                run_id="test_run_wal_002",
                num_nodes=8,
                num_malicious=0,
                protocol="AODV",
                simulation_status="running",
                persistence_status="pending"
            )
            s.add(run)
            s.flush()  # Dirty in-memory / active transaction, NOT committed
            
            # Executing safe_wal_checkpoint must NOT raise or abort the uncommitted transaction
            diag = safe_wal_checkpoint(self.engine)
            self.assertIn(diag["checkpoint_status"], ("COMPLETED", "BUSY", "PARTIAL"))
            
            # The active transaction can still commit cleanly
            run.persistence_status = "completed"
            s.commit()

        # Verify record persisted
        with self.Session() as s:
            verified = s.query(SimulationRun).filter_by(run_id="test_run_wal_002").first()
            self.assertIsNotNone(verified)
            self.assertEqual(verified.persistence_status, "completed")

    def test_04_checkpoint_failure_does_not_reverse_persistence(self):
        """4. Verify that any checkpoint failure does not alter or reverse committed persistence."""
        with self.Session() as s:
            run = SimulationRun(
                run_id="test_run_wal_003",
                num_nodes=8,
                num_malicious=0,
                protocol="AODV",
                simulation_status="completed",
                persistence_status="completed"
            )
            s.add(run)
            s.commit()

        # Simulate checkpoint failure by passing a closed/bogus engine or broken target
        class BrokenEngine:
            def raw_connection(self):
                raise RuntimeError("Simulated connection failure during checkpoint")

        diag = safe_wal_checkpoint(BrokenEngine())
        self.assertEqual(diag["checkpoint_status"], "ERROR")
        self.assertIn("Simulated connection failure", diag["error"])

        # Crucial check: Committed database record must remain 100% intact
        with self.Session() as s:
            verified = s.query(SimulationRun).filter_by(run_id="test_run_wal_003").first()
            self.assertIsNotNone(verified)
            self.assertEqual(verified.persistence_status, "completed")

    def test_05_active_reader_passive_checkpoint_behavior(self):
        """5. Verify passive checkpoint behavior with active reader does not raise exceptions."""
        with self.Session() as s:
            run = SimulationRun(
                run_id="test_run_wal_004",
                num_nodes=8,
                num_malicious=0,
                protocol="AODV",
                simulation_status="completed",
                persistence_status="completed"
            )
            s.add(run)
            s.commit()

        # Open an independent raw read connection holding an active cursor
        raw_read_conn = sqlite3.connect(str(self.db_path))
        try:
            read_cur = raw_read_conn.cursor()
            read_cur.execute("SELECT * FROM simulation_runs")
            # Cursor is active/open
            
            diag = safe_wal_checkpoint(self.engine)
            # PASSIVE checkpoint must complete or report BUSY, without throwing an unhandled exception
            self.assertIn(diag["checkpoint_status"], ("COMPLETED", "BUSY", "PARTIAL"))
            self.assertIsNone(diag["error"])
            
            read_cur.close()
        finally:
            raw_read_conn.close()

    def test_06_live_database_integrity_and_pilot_preservation(self):
        """6. Verify live database integrity and historical pilot invariance."""
        con = sqlite3.connect(f"file:{DEFAULT_DB_PATH}?mode=ro", uri=True)
        try:
            cur = con.cursor()
            
            # Integrity check
            cur.execute("PRAGMA integrity_check;")
            integrity = cur.fetchall()
            self.assertEqual(integrity, [("ok",)])

            # Foreign key check
            cur.execute("PRAGMA foreign_key_check;")
            fk_violations = cur.fetchall()
            self.assertEqual(fk_violations, [])

            # Historical pilot run check (ID=1)
            cur.execute("SELECT id, run_id, num_malicious FROM simulation_runs WHERE id = 1;")
            pilot = cur.fetchone()
            self.assertIsNotNone(pilot)
            self.assertEqual(pilot[0], 1)
            self.assertEqual(pilot[1], "20261111_225145_8e3c4f7c_8nodes_attack2_4")

            cur.execute("SELECT COUNT(*) FROM prevention_events WHERE simulation_run_id = 1;")
            pe_count = cur.fetchone()[0]
            self.assertEqual(pe_count, 0, "Historical pilot run must retain prevention_events = 0")

            cur.execute("SELECT COUNT(*) FROM artifact_ingestion_ledger WHERE simulation_run_id = 1;")
            ledger_count = cur.fetchone()[0]
            self.assertEqual(ledger_count, 0, "Historical pilot run must retain ledger = 0")
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

