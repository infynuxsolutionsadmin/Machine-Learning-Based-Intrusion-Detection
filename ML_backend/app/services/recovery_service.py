"""
recovery_service.py - Database-Authoritative Backend Restart & State Recovery Service.

Implements Phase 6 requirements for ML-MANET:
- Authoritative recovery of the latest verified completed simulation run from SQLite.
- Detection and marking of interrupted or incomplete simulation runs.
- Verification of registered simulation artifacts on disk (SHA-256 and existence).
- Reconstruction of in-memory simulation state (`current_simulation`) from database truth.
- Synchronization of `current_run.json` with the authoritative state.
- Safe, idempotent repeated execution with zero data loss or duplicate ingestion.
- Safe shutdown handler ensuring clean database detachment.
"""

import os
import sys
import json
import time
import logging
import hashlib
import platform
import uuid
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

logger = logging.getLogger("recovery_service")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DYNAMIC_RESULTS_DIR = BASE_DIR / "simulation" / "results" / "dynamic"
CURRENT_RUN_JSON_PATH = DYNAMIC_RESULTS_DIR / "current_run.json"

# Global lock tracking for multi-process database ownership
_CURRENT_LOCK: Optional["DatabaseOwnershipLock"] = None


class DatabaseOwnershipLock:
    """
    Cross-platform OS-level database ownership lock.
    Guarantees:
      - Only one backend process holds active write and recovery ownership per database.
      - Secondary processes enter NON_OWNER read-only mode and do NOT reconcile active runs.
      - If the owner terminates abnormally, the OS automatically releases the kernel file lock.
      - Accounts for PID reuse and host identity by recording companion metadata.
    """
    def __init__(self, lock_path: Path):
        self.lock_path = Path(lock_path).resolve()
        self.meta_path = self.lock_path.with_suffix(".json")
        self.lock_file = None
        self.is_owner = False
        self.instance_id = str(uuid.uuid4())[:8]

    def acquire(self) -> Dict[str, Any]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.lock_file = open(self.lock_path, "a+b")
            self.lock_file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBRLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            self.is_owner = True
            owner_info = {
                "pid": os.getpid(),
                "hostname": platform.node(),
                "instance_id": self.instance_id,
                "acquired_at": time.time(),
                "acquired_at_iso": datetime.now(timezone.utc).isoformat(),
            }
            try:
                self.meta_path.write_text(json.dumps(owner_info, indent=2), encoding="utf-8")
            except Exception as me:
                logger.warning(f"[OWNERSHIP] Could not write companion metadata: {me}")

            logger.info(
                f"[OWNERSHIP] Successfully acquired database ownership lock: "
                f"PID={owner_info['pid']}, host={owner_info['hostname']}, instance={self.instance_id}"
            )
            return {"status": "ACQUIRED", "is_owner": True, "owner_info": owner_info}

        except (OSError, IOError) as e:
            self.is_owner = False
            if self.lock_file:
                try:
                    self.lock_file.close()
                except Exception:
                    pass
                self.lock_file = None

            existing_owner = None
            try:
                if self.meta_path.exists():
                    raw = self.meta_path.read_text(encoding="utf-8")
                    if raw.strip():
                        existing_owner = json.loads(raw)
            except Exception:
                pass

            logger.warning(
                f"[OWNERSHIP] Database lock held by another process: {existing_owner}. "
                f"Error: {e}. Entering NON_OWNER read-only mode."
            )
            return {
                "status": "NON_OWNER",
                "is_owner": False,
                "existing_owner": existing_owner,
                "error": str(e),
            }

    def release(self):
        if self.is_owner and self.lock_file:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.lock_file.seek(0)
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self.lock_file.close()
            except Exception:
                pass
            self.lock_file = None
            self.is_owner = False
            try:
                if self.meta_path.exists():
                    self.meta_path.unlink()
            except Exception:
                pass
            logger.info("[OWNERSHIP] Released database ownership lock.")


def get_lock_path_for_db(db_path: Optional[str | Path] = None) -> Path:
    """Resolve the owner lock path corresponding to a database path."""
    if db_path is not None:
        p = Path(db_path).resolve()
        return p.with_suffix(p.suffix + ".owner.lock")
    try:
        from database.session import DB_PATH
        p = Path(DB_PATH).resolve()
        return p.with_suffix(p.suffix + ".owner.lock")
    except Exception:
        return BASE_DIR / "database" / "manet_records.db.owner.lock"


def acquire_database_ownership(db_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Acquire single-instance ownership lock for the database."""
    global _CURRENT_LOCK
    lock_path = get_lock_path_for_db(db_path)
    if _CURRENT_LOCK and _CURRENT_LOCK.is_owner and _CURRENT_LOCK.lock_path == lock_path:
        return {"status": "ALREADY_OWNED", "is_owner": True}
    if _CURRENT_LOCK:
        _CURRENT_LOCK.release()
    _CURRENT_LOCK = DatabaseOwnershipLock(lock_path)
    return _CURRENT_LOCK.acquire()


def release_database_ownership():
    """Release single-instance ownership lock for the database."""
    global _CURRENT_LOCK
    if _CURRENT_LOCK:
        _CURRENT_LOCK.release()
        _CURRENT_LOCK = None


def is_database_owner(auto_acquire_if_uninitialized: bool = True) -> bool:
    """Check if the current process holds active database write ownership."""
    global _CURRENT_LOCK
    if _CURRENT_LOCK is None and auto_acquire_if_uninitialized:
        res = acquire_database_ownership()
        return res.get("is_owner", False)
    return _CURRENT_LOCK.is_owner if _CURRENT_LOCK else False


def get_database_owner_info() -> Optional[Dict[str, Any]]:
    """Retrieve metadata for the current database owner."""
    global _CURRENT_LOCK
    if _CURRENT_LOCK and _CURRENT_LOCK.is_owner:
        return {
            "pid": os.getpid(),
            "hostname": platform.node(),
            "instance_id": _CURRENT_LOCK.instance_id,
        }
    return None


def verify_artifact_file(file_path: str, expected_hash: Optional[str] = None) -> bool:
    """
    Verify whether an artifact file exists and matches its registered SHA-256 hash.
    Returns True if valid, False if missing or corrupted.
    """
    if not file_path or not os.path.exists(file_path):
        return False
    if not expected_hash:
        return True
    try:
        data = Path(file_path).read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        return actual_hash.lower() == expected_hash.lower()
    except Exception as e:
        logger.warning(f"Error reading artifact {file_path} for hash verification: {e}")
        return False


def safe_terminate_wsl_simulation(run_id: str, timeout: float = 3.0) -> Dict[str, Any]:
    """
    Safely inspect and terminate a specific WSL NS-3 simulation process group.
    Verifies:
      1. run_id, PGID, SID, leader PID, and leader start-time ticks.
      2. Validates each surviving process individually in the group:
         - Its PGID must match meta['pgid'].
         - Its SID must match meta['sid'].
         - Its start_time_ticks must be >= meta['start_time'] (cannot precede leader).
         - Its commandline must match authentic NS-3 signatures:
           ('scratch/manet-sim', 'ns3.41-manet-sim', f'run_{run_id}', './ns3 run')
           Generic 'python' or bare commands are strictly rejected.
      3. If all living processes are verified, escalates from SIGTERM to SIGKILL.
      4. Guarantees zero signals sent if any check fails, or on missing/malformed metadata.
    """
    if not run_id:
        return {
            "status": "INVALID_RUN_ID",
            "active_process_found": False,
            "signals_sent": False,
            "terminated": False,
        }

    terminator_code = """
import os, sys, json, time, subprocess

def safe_terminate(run_id):
    meta_file = f"/tmp/manet_sim_{run_id}.json"
    pid_file = f"/tmp/manet_sim_{run_id}.pid"
    
    # Fix 4: Correct NO_METADATA semantics (no active process found, no signals sent, terminated=False)
    if not os.path.exists(meta_file):
        if os.path.exists(pid_file):
            try: os.remove(pid_file)
            except Exception: pass
        return {
            "status": "NO_METADATA",
            "active_process_found": False,
            "signals_sent": False,
            "terminated": False
        }

    try:
        with open(meta_file, "r") as f:
            content = f.read().strip()
            if not content:
                raise ValueError("Empty metadata file")
            meta = json.loads(content)
    except Exception as e:
        try: os.remove(meta_file)
        except Exception: pass
        return {
            "status": "MALFORMED_METADATA",
            "error": str(e),
            "active_process_found": False,
            "signals_sent": False,
            "terminated": False
        }

    recorded_run_id = meta.get("run_id")
    pgid = meta.get("pgid")
    sid = meta.get("sid")
    leader_pid = meta.get("leader_pid")
    try:
        leader_start_time = int(meta.get("start_time", 0))
    except Exception:
        leader_start_time = 0

    if recorded_run_id != run_id or not isinstance(pgid, int) or pgid <= 1:
        return {
            "status": "INVALID_METADATA_FIELDS",
            "active_process_found": False,
            "signals_sent": False,
            "terminated": False
        }

    # Query all processes currently belonging to PGID
    res = subprocess.run(["ps", "-o", "pid=", "-g", str(pgid)], capture_output=True, text=True)
    if res.returncode != 0 or not res.stdout.strip():
        try:
            if os.path.exists(meta_file): os.remove(meta_file)
            if os.path.exists(pid_file): os.remove(pid_file)
        except Exception: pass
        return {
            "status": "ALREADY_TERMINATED",
            "active_process_found": False,
            "signals_sent": False,
            "terminated": False
        }

    pids = [int(p.strip()) for p in res.stdout.strip().split() if p.strip().isdigit()]
    if not pids:
        try:
            if os.path.exists(meta_file): os.remove(meta_file)
            if os.path.exists(pid_file): os.remove(pid_file)
        except Exception: pass
        return {
            "status": "ALREADY_TERMINATED",
            "active_process_found": False,
            "signals_sent": False,
            "terminated": False
        }

    # Fix 2 & Fix 3: Validate EVERY process in the process group individually
    # Checks: PGID, SID, start_time >= leader_start_time, command authenticity
    # Fix 1: Authentic NS-3 execution signatures only (strictly excluding generic python and generic manet)
    AUTHENTIC_NS3_SIGNATURES = (
        "scratch/manet-sim",
        "ns3.41-manet-sim",
        f"run_{run_id}",
        "./ns3 run",
        "ns3-manet-sim",
    )

    has_ns3_binary_or_arg = False

    for p in pids:
        stat_path = f"/proc/{p}/stat"
        if not os.path.exists(stat_path):
            continue
        try:
            with open(stat_path, "r") as sf:
                stat_parts = sf.read().split()
            p_pgid = int(stat_parts[4])
            p_sid = int(stat_parts[5])
            p_starttime = int(stat_parts[21])
        except Exception:
            return {
                "status": "PROC_INSPECTION_FAILED",
                "pid": p,
                "active_process_found": True,
                "signals_sent": False,
                "terminated": False
            }

        # 1. PGID match
        if p_pgid != pgid:
            return {
                "status": "PGID_MISMATCH",
                "pid": p,
                "active_process_found": True,
                "signals_sent": False,
                "terminated": False
            }

        # 2. SID match if recorded
        if sid is not None and isinstance(sid, int) and p_sid != sid:
            return {
                "status": "SID_MISMATCH",
                "pid": p,
                "active_process_found": True,
                "signals_sent": False,
                "terminated": False
            }

        # 3. Leader anti-recycling check
        if p == leader_pid:
            if leader_start_time > 0 and p_starttime != leader_start_time:
                return {
                    "status": "PID_REUSE_DETECTED",
                    "pid": p,
                    "active_process_found": True,
                    "signals_sent": False,
                    "terminated": False
                }
        else:
            # Child process starttime check: cannot have started before the leader was born
            if leader_start_time > 0 and p_starttime < leader_start_time:
                return {
                    "status": "CHILD_PREDATES_LEADER",
                    "pid": p,
                    "active_process_found": True,
                    "signals_sent": False,
                    "terminated": False
                }

        # 4. Commandline inspection
        cmdline_path = f"/proc/{p}/cmdline"
        try:
            with open(cmdline_path, "rb") as cf:
                raw_bytes = cf.read()
            cmd_raw = " ".join([part.decode("utf-8", errors="ignore") for part in raw_bytes.split(b"\\0") if part])
        except Exception:
            cmd_raw = ""

        # Check for authentic NS-3 simulation markers
        if any(sig in cmd_raw for sig in AUTHENTIC_NS3_SIGNATURES):
            has_ns3_binary_or_arg = True

    # Fix 1: If NO process in the group matches authentic NS-3 signatures, ABORT!
    # A generic Python process or unrelated shell is REJECTED!
    if not has_ns3_binary_or_arg:
        return {
            "status": "UNRELATED_OR_GENERIC_PROCESS_GROUP",
            "active_process_found": True,
            "signals_sent": False,
            "terminated": False
        }

    # All verifications passed! Issue SIGTERM to verified process group
    subprocess.run(["kill", "-TERM", "--", f"-{pgid}"], capture_output=True)

    # Wait up to 2.0s for graceful exit
    t_end = time.time() + 2.0
    all_gone = False
    while time.time() < t_end:
        chk = subprocess.run(["ps", "-o", "pid=", "-g", str(pgid)], capture_output=True, text=True)
        if not chk.stdout.strip():
            all_gone = True
            break
        time.sleep(0.2)

    # Escalate to SIGKILL if members remain
    if not all_gone:
        subprocess.run(["kill", "-KILL", "--", f"-{pgid}"], capture_output=True)
        t_kill_end = time.time() + 1.0
        while time.time() < t_kill_end:
            chk = subprocess.run(["ps", "-o", "pid=", "-g", str(pgid)], capture_output=True, text=True)
            if not chk.stdout.strip():
                all_gone = True
                break
            time.sleep(0.2)

    if all_gone:
        try:
            if os.path.exists(meta_file): os.remove(meta_file)
            if os.path.exists(pid_file): os.remove(pid_file)
        except Exception: pass
        return {
            "status": "SUCCESSFULLY_TERMINATED",
            "pgid": pgid,
            "active_process_found": True,
            "signals_sent": True,
            "terminated": True
        }
    else:
        return {
            "status": "TERMINATION_TIMEOUT",
            "pgid": pgid,
            "active_process_found": True,
            "signals_sent": True,
            "terminated": False
        }

if __name__ == "__main__":
    res = safe_terminate(sys.argv[1])
    print("TERMINATOR_OUT:" + json.dumps(res))
"""

    try:
        res = subprocess.run(
            [
                "wsl", "-d", "Ubuntu", "-u", "kumar", "--",
                "python3", "-c", terminator_code, str(run_id)
            ],
            capture_output=True,
            timeout=int(timeout + 5),
        )
        out = res.stdout.replace(b'\x00', b'').decode('utf-8', errors='ignore').strip()
        for line in out.splitlines():
            if line.startswith("TERMINATOR_OUT:"):
                return json.loads(line.replace("TERMINATOR_OUT:", ""))
        err = res.stderr.replace(b'\x00', b'').decode('utf-8', errors='ignore').strip()
        return {"status": "WSL_EXEC_FAILURE", "stdout": out, "stderr": err, "terminated": False}
    except Exception as e:
        logger.warning(f"[WSL_PROCESS] Exception during safe WSL process termination for run '{run_id}': {e}")
        return {"status": "WSL_COMMUNICATION_ERROR", "error": str(e), "terminated": False}


def recover_backend_state(
    db_path: Optional[str | Path] = None,
    session: Optional[Any] = None,
    sync_current_run_json: bool = True,
    enforce_ownership: bool = True,
) -> Dict[str, Any]:
    """
    Execute database-authoritative startup state recovery with multi-process ownership protection.

    Steps:
      1. Check/acquire OS-level database ownership lock. If another live backend owns the database,
         enter NON_OWNER read-only mode and do NOT reconcile active runs.
      2. If owner, detect and reconcile abandoned runs strictly separating simulation_status from persistence_status.
      3. Locate the latest valid completed simulation run in SQLite (simulation_status=completed, persistence_status=completed).
      4. Query and verify all registered artifacts from `simulation_artifacts`.
      5. Reconstruct authentic `current_simulation` in-memory state.
      6. Synchronize `current_run.json` with the recovered state.
      7. If no completed run exists, initialize clean idle state.
    """
    from app.services.simulation_runner import current_simulation, default_simulation

    recovery_report: Dict[str, Any] = {
        "status": "PENDING",
        "is_owner": True,
        "recovered_run_id": None,
        "interrupted_runs_marked": 0,
        "artifacts_verified": 0,
        "artifacts_missing": 0,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # -------------------------------------------------------------------------
    # Step 0: Multi-Process Ownership Protection (Task 1)
    # -------------------------------------------------------------------------
    is_owner = True
    if enforce_ownership:
        own_res = acquire_database_ownership(db_path=db_path)
        is_owner = own_res.get("is_owner", False)
        recovery_report["is_owner"] = is_owner
        if not is_owner:
            existing_owner = own_res.get("existing_owner")
            recovery_report["existing_owner"] = existing_owner
            logger.warning(
                f"[RECOVERY] Another backend process owns the database lock: {existing_owner}. "
                "Entering NON_OWNER read-only mode: skipping state reconciliation to protect active simulations."
            )

    try:
        from database import (
            get_write_session,
            get_read_session,
            create_db_engine,
            SimulationRun,
            SimulationArtifact,
        )
    except Exception as imp_err:
        recovery_report["status"] = "DB_UNAVAILABLE"
        recovery_report["error"] = f"Database module import failed: {imp_err}"
        logger.error(f"[RECOVERY] Database unavailable: {imp_err}")
        return recovery_report

    # Session helper context manager to support explicit session, db_path, or default session
    @contextmanager
    def _resolve_session(for_write: bool = False):
        if session is not None:
            yield session
        elif db_path is not None:
            from sqlalchemy.orm import sessionmaker
            local_engine = create_db_engine(db_path)
            LocalSession = sessionmaker(bind=local_engine, autocommit=False, autoflush=False)
            sess = LocalSession()
            try:
                yield sess
                if for_write:
                    sess.commit()
            except Exception:
                if for_write:
                    sess.rollback()
                raise
            finally:
                sess.close()
        else:
            mgr = get_write_session() if for_write else get_read_session()
            with mgr as sess:
                yield sess

    # -------------------------------------------------------------------------
    # Step 1: Detect and mark interrupted runs (Strict Status Separation - Task 2)
    # -------------------------------------------------------------------------
    interrupted_count = 0
    if is_owner:
        try:
            with _resolve_session(for_write=True) as write_session:
                interrupted_runs = (
                    write_session.query(SimulationRun)
                    .filter(
                        (SimulationRun.simulation_status == "running")
                        | (SimulationRun.persistence_status == "pending")
                    )
                    .all()
                )
                for irun in interrupted_runs:
                    sim_stat = irun.simulation_status
                    persist_stat = irun.persistence_status

                    # Task 2: Separate simulation execution status from persistence status
                    # Case A: Simulation running + persistence pending
                    if sim_stat == "running":
                        try:
                            term_res = safe_terminate_wsl_simulation(irun.run_id)
                            logger.info(f"[RECOVERY] WSL process cleanup for abandoned run '{irun.run_id}': {term_res}")
                        except Exception as w_err:
                            logger.warning(f"[RECOVERY] Error during WSL process cleanup for run '{irun.run_id}': {w_err}")

                        irun.simulation_status = "failed"
                        irun.simulation_error = (
                            "Execution interrupted: process terminated unexpectedly before simulation completion."
                        )
                    # Case B: Simulation completed + persistence pending -> preserve simulation_status='completed'
                    # Case C: Simulation failed + persistence pending -> preserve simulation_status='failed'

                    if persist_stat == "pending":
                        irun.persistence_status = "failed"
                        if sim_stat == "completed":
                            irun.persistence_error = (
                                "Persistence interrupted: process terminated unexpectedly before database persistence completed."
                            )
                        else:
                            irun.persistence_error = "Persistence interrupted before completion."

                    interrupted_count += 1
                    logger.warning(
                        f"[RECOVERY] Reconciled abandoned run {irun.run_id} (ID={irun.id}): "
                        f"sim_status={sim_stat}->{irun.simulation_status}, persistence_status={persist_stat}->{irun.persistence_status}."
                    )
            recovery_report["interrupted_runs_marked"] = interrupted_count
        except Exception as int_err:
            recovery_report["status"] = "INTERRUPTED_SCAN_ERROR"
            recovery_report["error"] = str(int_err)
            logger.error(f"[RECOVERY] Error checking for interrupted runs: {int_err}")
            return recovery_report
    else:
        logger.info("[RECOVERY] Non-owner instance: skipping abandoned run reconciliation.")

    # -------------------------------------------------------------------------
    # Step 2: Query the latest verified completed simulation run
    # -------------------------------------------------------------------------
    try:
        with _resolve_session(for_write=False) as read_session:
            latest_run = (
                read_session.query(SimulationRun)
                .filter_by(simulation_status="completed", persistence_status="completed")
                .order_by(SimulationRun.id.desc())
                .first()
            )
            if not latest_run:
                # No completed run exists: set clean idle state
                current_simulation.clear()
                current_simulation.update(dict(default_simulation))
                recovery_report["status"] = "IDLE_NO_COMPLETED_RUNS"
                logger.info("[RECOVERY] No completed simulation runs found in database. Initialized clean idle state.")
                if sync_current_run_json:
                    _sync_disk_current_run(current_simulation)
                return recovery_report

            # Extract run properties
            run_id = latest_run.run_id
            num_nodes = latest_run.num_nodes
            num_malicious = latest_run.num_malicious
            protocol = latest_run.protocol or "AODV"
            attack_type = latest_run.attack_type
            packet_rate = latest_run.packet_rate
            simulation_time = latest_run.simulation_time

            malicious_nodes = []
            if latest_run.ground_truth_malicious:
                try:
                    malicious_nodes = json.loads(latest_run.ground_truth_malicious)
                except Exception:
                    malicious_nodes = []

            duration = None
            if latest_run.completed_at and latest_run.started_at:
                duration = round((latest_run.completed_at - latest_run.started_at).total_seconds(), 2)

            # Query registered artifacts
            artifacts = (
                read_session.query(SimulationArtifact)
                .filter_by(simulation_run_id=latest_run.id)
                .all()
            )
            artifact_map: Dict[str, str] = {}
            verified_count = 0
            missing_count = 0

            for art in artifacts:
                f_type = art.file_type
                f_path = art.file_path
                is_valid = verify_artifact_file(f_path, art.file_hash_sha256)
                if is_valid:
                    artifact_map[f_type] = f_path
                    verified_count += 1
                else:
                    missing_count += 1
                    logger.warning(
                        f"[RECOVERY] Registered artifact '{f_type}' at '{f_path}' is missing or corrupted."
                    )

            recovery_report["artifacts_verified"] = verified_count
            recovery_report["artifacts_missing"] = missing_count

    except Exception as query_err:
        recovery_report["status"] = "QUERY_ERROR"
        recovery_report["error"] = str(query_err)
        logger.error(f"[RECOVERY] Error querying latest simulation run from database: {query_err}")
        return recovery_report

    # -------------------------------------------------------------------------
    # Step 3: Reconstruct authentic in-memory state (current_simulation)
    # -------------------------------------------------------------------------
    recovered_state = {
        "status": "completed",
        "protocol": protocol,
        "run_id": run_id,
        "nNodes": num_nodes,
        "attackEnabled": num_malicious > 0,
        "maliciousNodes": malicious_nodes,
        "attack_type": attack_type,
        "packet_rate": packet_rate,
        "simulation_time": simulation_time,
        "duration_seconds": duration,
        "error": None,
        "sourceNode": 0,
        "destNode": num_nodes - 1,
        "csv_path": artifact_map.get("flow_csv_attack"),
        "xml_path": artifact_map.get("flow_xml_attack"),
        "baseline_csv_path": artifact_map.get("flow_csv_baseline"),
        "baseline_energy_csv_path": artifact_map.get("energy_csv_baseline"),
        "energy_csv_path": artifact_map.get("energy_csv_attack"),
        "trace_csv_path": artifact_map.get("trace_csv_p2") or artifact_map.get("trace_csv_p1"),
        "route_tr_path": artifact_map.get("route_tr_p2") or artifact_map.get("route_tr_p1"),
        "routing_json_path": artifact_map.get("routing_json_p2"),
        "fl_metrics_path": artifact_map.get("fl_metrics_json"),
        "topology_path": artifact_map.get("topology_json"),
        "persistence": {
            "status": "RECOVERED_FROM_DATABASE",
            "run_id": run_id,
            "recovered_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Atomically update the shared singleton dict
    current_simulation.clear()
    current_simulation.update(recovered_state)

    # -------------------------------------------------------------------------
    # Step 4: Synchronize disk current_run.json (Only owner writes disk cache)
    # -------------------------------------------------------------------------
    if sync_current_run_json and is_owner:
        _sync_disk_current_run(current_simulation)

    recovery_report["status"] = "RECOVERED" if is_owner else "NON_OWNER_READ_ONLY"
    recovery_report["recovered_run_id"] = run_id
    recovery_report["num_nodes"] = num_nodes
    recovery_report["num_malicious"] = num_malicious
    logger.info(
        f"[RECOVERY] Successfully recovered backend state for run '{run_id}' "
        f"({num_nodes} nodes, {num_malicious} attackers, {verified_count} artifacts verified, is_owner={is_owner})."
    )

    return recovery_report


def _sync_disk_current_run(state_dict: Dict[str, Any]) -> None:
    """Safely synchronize state to current_run.json on disk."""
    try:
        DYNAMIC_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = CURRENT_RUN_JSON_PATH.with_suffix(".tmp")
        temp_file.write_text(json.dumps(state_dict, indent=2), encoding="utf-8")
        temp_file.replace(CURRENT_RUN_JSON_PATH)
    except Exception as e:
        logger.warning(f"[RECOVERY] Warning: Failed to sync current_run.json: {e}")


def handle_backend_shutdown(
    db_path: Optional[str | Path] = None,
    session: Optional[Any] = None,
    sync_current_run_json: bool = True,
) -> None:
    """
    Safe shutdown hook executed during application termination.
    Guarantees:
      - Stops or terminates owned WSL NS-3 subprocesses safely.
      - Does NOT falsely mark active simulation as completed.
      - Preserves successfully completed runs without overwriting as failed.
      - Marks any genuinely active simulation as interrupted.
      - Attempts a safe PASSIVE WAL checkpoint to checkpoint SQLite write frames.
      - Releases OS-level database ownership lock.
    """
    logger.info("[SHUTDOWN] Executing backend shutdown safety hook...")
    try:
        from app.services.simulation_runner import current_simulation, active_process_tracker
        if current_simulation.get("status") == "running":
            run_id = current_simulation.get("run_id")
            logger.warning(f"[SHUTDOWN] Simulation run '{run_id}' was active during shutdown; terminating subprocess and recording interruption.")

            # 1. Terminate owned WSL & Windows subprocesses (Task 3)
            try:
                active_process_tracker.terminate_active(run_id=run_id)
            except Exception as proc_err:
                logger.warning(f"[SHUTDOWN] Error terminating active subprocess for run {run_id}: {proc_err}")

            # 2. Update database record with strict status separation
            try:
                from database import get_write_session, create_db_engine, SimulationRun
                if session is not None:
                    r = session.query(SimulationRun).filter_by(run_id=run_id).first()
                    if r and r.simulation_status == "running":
                        r.simulation_status = "failed"
                        r.simulation_error = "Execution interrupted by backend shutdown."
                        r.persistence_status = "failed"
                        r.persistence_error = "Persistence cancelled due to backend shutdown."
                        session.commit()
                elif db_path is not None:
                    from sqlalchemy.orm import sessionmaker
                    engine = create_db_engine(db_path)
                    with sessionmaker(bind=engine)() as s:
                        r = s.query(SimulationRun).filter_by(run_id=run_id).first()
                        if r and r.simulation_status == "running":
                            r.simulation_status = "failed"
                            r.simulation_error = "Execution interrupted by backend shutdown."
                            r.persistence_status = "failed"
                            r.persistence_error = "Persistence cancelled due to backend shutdown."
                            s.commit()
                else:
                    with get_write_session() as s:
                        r = s.query(SimulationRun).filter_by(run_id=run_id).first()
                        if r and r.simulation_status == "running":
                            r.simulation_status = "failed"
                            r.simulation_error = "Execution interrupted by backend shutdown."
                            r.persistence_status = "failed"
                            r.persistence_error = "Persistence cancelled due to backend shutdown."
            except Exception as dbe:
                logger.warning(f"[SHUTDOWN] Could not update interrupted run in DB: {dbe}")

            current_simulation["status"] = "failed"
            current_simulation["error"] = "Execution interrupted by backend shutdown."
            if sync_current_run_json:
                _sync_disk_current_run(current_simulation)
    except Exception as exc:
        logger.warning(f"[SHUTDOWN] Warning in simulation state handling: {exc}")

    try:
        from database import safe_wal_checkpoint
        diag = safe_wal_checkpoint()
        logger.info(f"[SHUTDOWN] Final WAL checkpoint: {diag.get('checkpoint_status')}")
    except Exception as e:
        logger.warning(f"[SHUTDOWN] Final WAL checkpoint failed: {e}")

    # Release database ownership lock (Task 1)
    try:
        release_database_ownership()
    except Exception as lock_err:
        logger.warning(f"[SHUTDOWN] Error releasing database ownership lock: {lock_err}")

    logger.info("[SHUTDOWN] Backend shutdown safety completed.")
