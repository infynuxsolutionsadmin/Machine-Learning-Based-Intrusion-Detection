"""
ingestion_service.py - Core Simulation Data Ingestion Service for MANET Database.
Handles Stage A (Run Registration) and Stage B (Core Ingestion: simulation_metrics,
node_energy_metrics, simulation_artifacts) using verified source parsers and atomic upserts.
"""
import csv
import hashlib
import json
import logging
import math
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .models import (
    ArtifactIngestionLedger,
    MLPrediction,
    ModelRegistry,
    NodeEnergyMetric,
    PreventionEvent,
    RoutingRecord,
    SimulationArtifact,
    SimulationMetric,
    SimulationRun,
    TrustEvaluation,
)
from .session import get_write_session

logger = logging.getLogger(__name__)

# Base path definitions
BACKEND_DIR = Path(__file__).resolve().parent.parent
DYNAMIC_RESULTS_DIR = BACKEND_DIR / "simulation" / "results" / "dynamic"
BASELINE_MODELS_DIR = BACKEND_DIR / "models" / "baseline"


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_run_started_at(
    run_id: str,
    source_tz_name: Optional[str] = None,
    fallback_file: Optional[Path] = None,
) -> datetime:
    """
    Parse canonical run_id timestamp prefix (YYYYMMDD_HHMMSS), interpret it
    in the explicitly established simulation source timezone, and return normalized UTC datetime.
    
    Resolution precedence:
      1. Explicit argument source_tz_name
      2. Environment variable SIMULATION_TIMEZONE
      3. Established simulation host timezone "Asia/Kolkata" (IST, UTC+05:30)

    Safety constraint (Phase B2.3):
      If run_id does not contain a canonical timestamp prefix (YYYYMMDD_HHMMSS),
      we strictly reject fallback to filesystem st_ctime or datetime.now() to prevent
      fabricating misleading simulation start times. Instead, a clear ValueError is raised.
    """
    ts_match = re.match(r"^(\d{8}_\d{6})", run_id)
    if not ts_match:
        raise ValueError(
            f"Cannot resolve authoritative simulation start timestamp for run '{run_id}'. "
            "Run ID lacks canonical 'YYYYMMDD_HHMMSS' prefix and no authoritative start-time "
            "metadata exists. Ingestion refused to prevent timestamp fabrication."
        )

    ts_str = ts_match.group(1)
    dt_naive = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")

    tz_name = (
        source_tz_name
        or os.environ.get("SIMULATION_TIMEZONE")
        or "Asia/Kolkata"
    )
    try:
        import zoneinfo
        source_tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        source_tz = datetime.now().astimezone().tzinfo or timezone.utc

    # Localize to established source timezone and convert to UTC
    dt_local = dt_naive.replace(tzinfo=source_tz)
    return dt_local.astimezone(timezone.utc)


def extract_run_metadata(
    run_id: str,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR,
    source_tz_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract and validate metadata for a simulation run strictly from authentic source files.
    Does not invent default values for missing attributes.
    """
    current_run_path = dynamic_dir / "current_run.json"
    routing_json_path = dynamic_dir / f"run_{run_id}_routing.json"

    current_run_data = {}
    if current_run_path.exists():
        try:
            with open(current_run_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if loaded.get("run_id") == run_id:
                    current_run_data = loaded
        except Exception as e:
            logger.warning(f"Failed to read current_run.json for {run_id}: {e}")

    # Extract protocol strictly from verified routing JSON
    protocol = None
    if routing_json_path.exists():
        try:
            with open(routing_json_path, "r", encoding="utf-8") as f:
                r_data = json.load(f)
                protocol = r_data.get("protocol")
        except Exception as e:
            logger.warning(f"Failed to read protocol from {routing_json_path}: {e}")

    # If protocol is not in routing.json, check current_run
    if not protocol and "protocol" in current_run_data:
        protocol = current_run_data.get("protocol")

    if not protocol:
        raise ValueError(
            f"Cannot resolve authoritative routing protocol for run {run_id} from source files."
        )

    # Node counts
    num_nodes = current_run_data.get("nNodes")
    if num_nodes is None and routing_json_path.exists():
        try:
            with open(routing_json_path, "r", encoding="utf-8") as f:
                num_nodes = json.load(f).get("nNodes")
        except Exception:
            pass

    if num_nodes is None or num_nodes < 2:
        raise ValueError(f"Invalid or missing node count for run {run_id}")

    malicious_nodes = current_run_data.get("maliciousNodes")
    if malicious_nodes is None or not isinstance(malicious_nodes, list):
        # Fallback: Parse from run_id format: e.g. run_YYYYMMDD_HHMMSS_<hash>_<N>nodes_attack2_4
        import re
        m = re.search(r'_attack([0-9_]+)$', run_id)
        if m:
            try:
                malicious_nodes = [int(x) for x in m.group(1).split('_') if x.isdigit()]
            except Exception:
                malicious_nodes = []
        else:
            malicious_nodes = []
    num_malicious = len(malicious_nodes) if isinstance(malicious_nodes, list) else 0

    # Simulation Status
    sim_status = current_run_data.get("status", "completed")
    if sim_status not in ("running", "completed", "failed"):
        raise ValueError(f"Unrecognized simulation status {sim_status} for run {run_id}")

    # Start timestamp normalized to UTC using established source timezone
    fallback_path = routing_json_path if routing_json_path.exists() else dynamic_dir
    started_at = resolve_run_started_at(
        run_id,
        source_tz_name=source_tz_name,
        fallback_file=fallback_path,
    )

    # Note: completed_at is left None unless an authoritative finish timestamp exists in source
    # attack_type is left None if inferred, or taken from source if explicitly set
    attack_type = current_run_data.get("attackType")

    return {
        "run_id": run_id,
        "protocol": protocol,
        "num_nodes": int(num_nodes),
        "num_malicious": int(num_malicious),
        "attack_type": attack_type,
        "packet_rate": None,
        "simulation_time": None,
        "ground_truth_malicious": json.dumps(malicious_nodes) if malicious_nodes else None,
        "simulation_status": sim_status,
        "started_at": started_at,
        "completed_at": None,
    }


def parse_flow_metrics(
    csv_path: Path,
    xml_path: Path,
    phase: str
) -> List[Dict[str, Any]]:
    """
    Parse flow metrics combining CSV throughput/PDR metrics with exact XML byte and jitter values.
    Raises FileNotFoundError if XML or CSV is missing.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Flow CSV file missing: {csv_path}")
    if not xml_path.exists():
        raise FileNotFoundError(f"FlowMonitor XML file missing: {xml_path}")

    # Parse FlowMonitor XML for exact bytes and jitter
    tree = ET.parse(xml_path)
    root = tree.getroot()

    xml_stats: Dict[int, Dict[str, Any]] = {}
    for flow in root.findall(".//FlowStats/Flow"):
        fid_val = flow.get("flowId")
        if not fid_val:
            continue
        fid = int(fid_val)
        tx_bytes = int(flow.get("txBytes", 0))
        rx_bytes = int(flow.get("rxBytes", 0))
        jitter_sum_str = flow.get("jitterSum", "0ns")
        jitter_ns = 0.0
        if jitter_sum_str:
            jitter_ns = float(jitter_sum_str.replace("+", "").replace("ns", ""))
        xml_stats[fid] = {
            "tx_bytes": tx_bytes,
            "rx_bytes": rx_bytes,
            "jitter_ns": jitter_ns,
        }

    records: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fid = int(row["flow_id"])
            if fid not in xml_stats:
                raise ValueError(
                    f"Flow {fid} in CSV {csv_path.name} not found in XML {xml_path.name}"
                )

            x = xml_stats[fid]
            tx_p = int(row["tx_packets"])
            rx_p = int(row["rx_packets"])
            lost_p = int(row["lost_packets"])
            pdr = float(row["pdr_percent"])
            tput = float(row["throughput_kbps"])
            delay = float(row["mean_delay_ms"])

            # Verified average jitter formula in milliseconds
            avg_jitter_ms = (x["jitter_ns"] / 1e6) / (rx_p - 1) if rx_p > 1 else 0.0
            packet_loss_ratio = (lost_p / tx_p * 100.0) if tx_p > 0 else 0.0

            records.append({
                "phase": phase,
                "flow_id": fid,
                "source_ip": row["source_addr"],
                "dest_ip": row["dest_addr"],
                "tx_packets": tx_p,
                "rx_packets": rx_p,
                "tx_bytes": x["tx_bytes"],
                "rx_bytes": x["rx_bytes"],
                "pdr": pdr,
                "throughput_kbps": tput,
                "avg_delay_ms": delay,
                "avg_jitter_ms": round(avg_jitter_ms, 4),
                "packet_loss_ratio": round(packet_loss_ratio, 4),
            })

    return records


def parse_energy_metrics(
    csv_path: Path,
    phase: str,
    num_nodes: int
) -> List[Dict[str, Any]]:
    """
    Parse per-node residual energy CSV and validate physical boundaries.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Energy CSV file missing: {csv_path}")

    records: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nid = int(row["node_id"])
            init_e = float(row["initial_energy"])
            rem_e = float(row["remaining_energy"])
            cons_e = float(row["consumed_energy"])
            res_pct = float(row["residual_percentage"])

            # Validations
            if not (0 <= nid < num_nodes):
                raise ValueError(f"Node ID {nid} outside node count {num_nodes}")
            if init_e < 0 or rem_e < 0 or cons_e < 0:
                raise ValueError(f"Negative energy metric encountered for node {nid}")
            if rem_e > init_e + 1e-4:
                raise ValueError(f"Remaining energy {rem_e} exceeds initial {init_e}")
            if not (-1e-4 <= res_pct <= 100.0 + 1e-4):
                raise ValueError(f"Residual percentage {res_pct} outside [0, 100]")

            records.append({
                "phase": phase,
                "node_id": nid,
                "initial_energy_j": init_e,
                "remaining_energy_j": rem_e,
                "consumed_energy_j": cons_e,
                "residual_pct": res_pct,
            })

    return records


def get_simulation_artifact_catalog(
    run_id: str,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR
) -> Dict[str, Path]:
    """
    Build the catalog of verified physical artifact paths for a given simulation run.
    """
    return {
        "flow_csv_attack": dynamic_dir / f"run_{run_id}.csv",
        "flow_xml_attack": dynamic_dir / f"run_{run_id}.xml",
        "flow_csv_baseline": dynamic_dir / run_id / "baseline" / f"run_{run_id}_baseline.csv",
        "flow_xml_baseline": dynamic_dir / run_id / "baseline" / f"run_{run_id}_baseline.xml",
        "energy_csv_attack": dynamic_dir / f"run_{run_id}_energy.csv",
        "energy_csv_baseline": dynamic_dir / run_id / "baseline" / f"run_{run_id}_baseline_energy.csv",
        "trace_csv_p1": dynamic_dir / f"run_{run_id}_trace.csv",
        "trace_csv_p2": dynamic_dir / f"run_{run_id}_trace_p2.csv",
        "route_tr_p1": dynamic_dir / f"run_{run_id}_route.tr",
        "route_tr_p2": dynamic_dir / f"run_{run_id}_route_p2.tr",
        "routing_json_p2": dynamic_dir / f"run_{run_id}_routing.json",
        "topology_json": dynamic_dir / f"run_{run_id}_topology.json",
        "lstm_pred_csv": dynamic_dir / f"run_{run_id}_lstm_pred.csv",
        "classical_ml_csv": dynamic_dir / f"run_{run_id}_classical_ml_predictions.csv",
        "fl_metrics_json": dynamic_dir / run_id / "fl" / "fl_metrics.json",
        "fl_global_model_pth": dynamic_dir / run_id / "fl" / "federated_global_model.pth",
        "prevention_events_json": dynamic_dir / f"run_{run_id}_prevention_events.json",
    }


def parse_artifact_records(
    run_id: str,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR
) -> List[Dict[str, Any]]:
    """
    Inspect, hash, and prepare artifact records for all existing files in the catalog.
    """
    catalog = get_simulation_artifact_catalog(run_id, dynamic_dir)
    records: List[Dict[str, Any]] = []

    for file_type, file_path in catalog.items():
        if not file_path.exists():
            continue

        file_size = os.path.getsize(file_path)
        file_hash = compute_file_sha256(file_path)
        norm_path = file_path.resolve().as_posix()

        records.append({
            "file_type": file_type,
            "file_path": norm_path,
            "file_size_bytes": file_size,
            "file_hash_sha256": file_hash,
        })

    return records


def ingest_simulation_core(
    run_id: str,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR,
    source_tz_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute Phase B2 core ingestion for a single simulation run.
    Follows the safe two-stage transaction lifecycle:
      Stage A: Register run (persistence_status = 'pending') in an isolated transaction.
      Stage B: Atomic upsert of flow metrics, energy metrics, and artifacts.
      Rollback & Failure Logging: On error, rolls back Stage B and records persistence_status='failed'.
    """
    logger.info(f"Starting Phase B2 core ingestion for run {run_id}")

    # 1. Validate metadata from authentic source files
    run_metadata = extract_run_metadata(run_id, dynamic_dir, source_tz_name=source_tz_name)
    num_nodes = run_metadata["num_nodes"]

    # 2. Stage A: Run Registration (Persistence Status = 'pending')
    run_db_id: Optional[int] = None
    with get_write_session() as session:
        stmt = sqlite_insert(SimulationRun).values(
            run_id=run_metadata["run_id"],
            protocol=run_metadata["protocol"],
            num_nodes=run_metadata["num_nodes"],
            num_malicious=run_metadata["num_malicious"],
            attack_type=run_metadata["attack_type"],
            packet_rate=run_metadata["packet_rate"],
            simulation_time=run_metadata["simulation_time"],
            ground_truth_malicious=run_metadata["ground_truth_malicious"],
            simulation_status=run_metadata["simulation_status"],
            persistence_status="pending",
            started_at=run_metadata["started_at"],
            completed_at=run_metadata["completed_at"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["run_id"],
            set_={
                "protocol": stmt.excluded.protocol,
                "num_nodes": stmt.excluded.num_nodes,
                "num_malicious": stmt.excluded.num_malicious,
                "attack_type": stmt.excluded.attack_type,
                "ground_truth_malicious": stmt.excluded.ground_truth_malicious,
                "simulation_status": stmt.excluded.simulation_status,
                "persistence_status": "pending",
                "persistence_error": None,
            },
        )
        session.execute(stmt)
        # Fetch the registered ID
        run_record = session.query(SimulationRun).filter_by(run_id=run_id).one()
        run_db_id = run_record.id

    if not run_db_id:
        raise RuntimeError(f"Failed to resolve database ID for run {run_id}")

    # 3. Stage B: Parse & Validate child records in memory before write
    catalog = get_simulation_artifact_catalog(run_id, dynamic_dir)

    try:
        # Flow metrics (attack and baseline)
        attack_flows = parse_flow_metrics(catalog["flow_csv_attack"], catalog["flow_xml_attack"], "attack")
        baseline_flows = parse_flow_metrics(catalog["flow_csv_baseline"], catalog["flow_xml_baseline"], "baseline")
        all_flows = attack_flows + baseline_flows

        # Energy metrics (attack and baseline)
        attack_energy = parse_energy_metrics(catalog["energy_csv_attack"], "attack", num_nodes)
        baseline_energy = parse_energy_metrics(catalog["energy_csv_baseline"], "baseline", num_nodes)
        all_energy = attack_energy + baseline_energy

        # Artifacts
        artifacts = parse_artifact_records(run_id, dynamic_dir)

        # Stage B Write Transaction
        with get_write_session() as session:
            # Upsert flow metrics
            for flow_item in all_flows:
                f_stmt = sqlite_insert(SimulationMetric).values(
                    simulation_run_id=run_db_id,
                    phase=flow_item["phase"],
                    flow_id=flow_item["flow_id"],
                    source_ip=flow_item["source_ip"],
                    dest_ip=flow_item["dest_ip"],
                    tx_packets=flow_item["tx_packets"],
                    rx_packets=flow_item["rx_packets"],
                    tx_bytes=flow_item["tx_bytes"],
                    rx_bytes=flow_item["rx_bytes"],
                    pdr=flow_item["pdr"],
                    throughput_kbps=flow_item["throughput_kbps"],
                    avg_delay_ms=flow_item["avg_delay_ms"],
                    avg_jitter_ms=flow_item["avg_jitter_ms"],
                    packet_loss_ratio=flow_item["packet_loss_ratio"],
                )
                f_stmt = f_stmt.on_conflict_do_update(
                    index_elements=["simulation_run_id", "phase", "flow_id"],
                    set_={
                        "source_ip": f_stmt.excluded.source_ip,
                        "dest_ip": f_stmt.excluded.dest_ip,
                        "tx_packets": f_stmt.excluded.tx_packets,
                        "rx_packets": f_stmt.excluded.rx_packets,
                        "tx_bytes": f_stmt.excluded.tx_bytes,
                        "rx_bytes": f_stmt.excluded.rx_bytes,
                        "pdr": f_stmt.excluded.pdr,
                        "throughput_kbps": f_stmt.excluded.throughput_kbps,
                        "avg_delay_ms": f_stmt.excluded.avg_delay_ms,
                        "avg_jitter_ms": f_stmt.excluded.avg_jitter_ms,
                        "packet_loss_ratio": f_stmt.excluded.packet_loss_ratio,
                    },
                )
                session.execute(f_stmt)

            # Upsert energy metrics
            for energy_item in all_energy:
                e_stmt = sqlite_insert(NodeEnergyMetric).values(
                    simulation_run_id=run_db_id,
                    phase=energy_item["phase"],
                    node_id=energy_item["node_id"],
                    initial_energy_j=energy_item["initial_energy_j"],
                    remaining_energy_j=energy_item["remaining_energy_j"],
                    consumed_energy_j=energy_item["consumed_energy_j"],
                    residual_pct=energy_item["residual_pct"],
                )
                e_stmt = e_stmt.on_conflict_do_update(
                    index_elements=["simulation_run_id", "phase", "node_id"],
                    set_={
                        "initial_energy_j": e_stmt.excluded.initial_energy_j,
                        "remaining_energy_j": e_stmt.excluded.remaining_energy_j,
                        "consumed_energy_j": e_stmt.excluded.consumed_energy_j,
                        "residual_pct": e_stmt.excluded.residual_pct,
                    },
                )
                session.execute(e_stmt)

            # Upsert artifacts
            for art_item in artifacts:
                a_stmt = sqlite_insert(SimulationArtifact).values(
                    simulation_run_id=run_db_id,
                    file_type=art_item["file_type"],
                    file_path=art_item["file_path"],
                    file_size_bytes=art_item["file_size_bytes"],
                    file_hash_sha256=art_item["file_hash_sha256"],
                )
                a_stmt = a_stmt.on_conflict_do_update(
                    index_elements=["simulation_run_id", "file_type"],
                    set_={
                        "file_path": a_stmt.excluded.file_path,
                        "file_size_bytes": a_stmt.excluded.file_size_bytes,
                        "file_hash_sha256": a_stmt.excluded.file_hash_sha256,
                    },
                )
                session.execute(a_stmt)

            # Update run to completed
            run_rec = session.query(SimulationRun).filter_by(id=run_db_id).one()
            run_rec.persistence_status = "completed"
            run_rec.persisted_at = datetime.now(timezone.utc)
            run_rec.persistence_error = None

        logger.info(
            f"Successfully persisted run {run_id}: {len(all_flows)} flows, "
            f"{len(all_energy)} energy nodes, {len(artifacts)} artifacts"
        )
        return {
            "status": "success",
            "run_id": run_id,
            "simulation_run_id": run_db_id,
            "flow_metrics_count": len(all_flows),
            "node_energy_count": len(all_energy),
            "artifacts_count": len(artifacts),
        }

    except Exception as exc:
        logger.error(f"Stage B core ingestion failed for run {run_id}: {exc}")
        # Secondary isolated transaction to record failure
        try:
            with get_write_session() as fail_session:
                failed_run = fail_session.query(SimulationRun).filter_by(id=run_db_id).first()
                if failed_run:
                    failed_run.persistence_status = "failed"
                    failed_run.persistence_error = str(exc)
        except Exception as sec_exc:
            logger.critical(
                f"Failed to record failure status for run {run_id}: {sec_exc}"
            )
        raise exc


def check_model_loadability(artifact_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Safely check if a model artifact can be loaded in the current runtime environment.
    Returns (True, None) if loadable, or (False, error_message) if dependencies are missing.
    """
    if not artifact_path.exists():
        return False, f"Artifact file does not exist: {artifact_path}"
    try:
        import joblib
        joblib.load(artifact_path)
        return True, None
    except Exception as e:
        return False, str(e)


def ingest_model_registry(
    models_dir: Optional[Path] = None,
    expected_hashes: Optional[Dict[str, str]] = None,
    include_inactive: bool = True,
    experiment_name: str = "baseline",
) -> Dict[str, Any]:
    """
    Register authentic classical ML model artifacts into the model_registry table.
    
    Preconditions:
      - Physical artifact files exist and are readable.
      - Hashes match physical file SHA-256 (and expected_hashes if supplied).
      - Training metrics are sourced directly from experiment_metadata.json.
      - Selected features are sourced from selected_features.json / experiment_metadata.json.
      - Loadable models (RandomForest, SVM, MLP) have is_active = True.
      - Models with missing runtime packages (XGBoost, CatBoost) have is_active = False if include_inactive=True.
      - Scaler and deep learning models are not registered as classical prediction models.
    
    Idempotency:
      - Uses sqlite_insert with on_conflict_do_update on (model_name, version_tag, file_hash_sha256).
    """
    logger.info("Starting Phase B3.2 model registry ingestion")

    if models_dir is None:
        models_dir = BASELINE_MODELS_DIR
    models_dir = Path(models_dir)

    if not models_dir.exists():
        raise FileNotFoundError(f"Model directory does not exist: {models_dir}")

    meta_path = models_dir / "experiment_metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Experiment metadata missing: {meta_path}")

    feat_path = models_dir / "selected_features.json"

    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    selected_features_list = []
    if feat_path.exists():
        with open(feat_path, "r", encoding="utf-8") as f:
            selected_features_list = json.load(f)
    elif "selected_features" in meta_data:
        selected_features_list = meta_data["selected_features"]

    selected_features_json = json.dumps(selected_features_list)

    classical_models = ["RandomForest", "SVM", "MLP", "XGBoost", "CatBoost"]
    registered_records = []

    for model_name in classical_models:
        artifact_file = models_dir / f"{model_name}.pkl"
        if not artifact_file.exists():
            raise FileNotFoundError(f"Model artifact file missing: {artifact_file}")

        file_size = artifact_file.stat().st_size
        if file_size == 0:
            raise ValueError(f"Model artifact file is empty: {artifact_file}")

        actual_hash = compute_file_sha256(artifact_file)
        if expected_hashes and model_name in expected_hashes:
            exp_hash = expected_hashes[model_name]
            if actual_hash != exp_hash:
                raise ValueError(
                    f"Hash mismatch for {model_name}: expected {exp_hash}, got {actual_hash}"
                )

        loadable, load_err = check_model_loadability(artifact_file)
        if not loadable and not include_inactive:
            logger.info(f"Skipping inactive/non-loadable model {model_name}: {load_err}")
            continue

        is_active = bool(loadable)

        # Retrieve training/evaluation metrics strictly from metadata
        model_metrics = meta_data.get("metrics", {}).get(model_name, {})
        accuracy = model_metrics.get("Accuracy")
        precision = model_metrics.get("Precision")
        recall = model_metrics.get("Recall")
        f1 = model_metrics.get("F1")
        fpr = model_metrics.get("FPR")
        loss = None  # Explicitly NULL for classical ML models

        cm = model_metrics.get("ConfusionMatrix")
        cm_json = json.dumps(cm) if cm is not None else None

        # Normalized relative path from ML_backend
        try:
            rel_path = artifact_file.relative_to(BACKEND_DIR).as_posix()
        except ValueError:
            rel_path = artifact_file.as_posix()

        registered_records.append({
            "model_name": model_name,
            "model_type": "classical_ml",
            "version_tag": experiment_name,
            "file_hash_sha256": actual_hash,
            "artifact_path": rel_path,
            "accuracy": float(accuracy) if accuracy is not None else None,
            "precision": float(precision) if precision is not None else None,
            "recall": float(recall) if recall is not None else None,
            "f1_score": float(f1) if f1 is not None else None,
            "fpr": float(fpr) if fpr is not None else None,
            "loss": loss,
            "selected_features": selected_features_json,
            "confusion_matrix": cm_json,
            "is_active": is_active,
            "loadable": loadable,
        })

    # Execute registration in an isolated write transaction
    with get_write_session() as session:
        for rec in registered_records:
            stmt = sqlite_insert(ModelRegistry).values(
                model_name=rec["model_name"],
                model_type=rec["model_type"],
                version_tag=rec["version_tag"],
                file_hash_sha256=rec["file_hash_sha256"],
                artifact_path=rec["artifact_path"],
                accuracy=rec["accuracy"],
                precision=rec["precision"],
                recall=rec["recall"],
                f1_score=rec["f1_score"],
                fpr=rec["fpr"],
                loss=rec["loss"],
                selected_features=rec["selected_features"],
                confusion_matrix=rec["confusion_matrix"],
                is_active=rec["is_active"],
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["model_name", "version_tag", "file_hash_sha256"],
                set_={
                    "artifact_path": stmt.excluded.artifact_path,
                    "accuracy": stmt.excluded.accuracy,
                    "precision": stmt.excluded.precision,
                    "recall": stmt.excluded.recall,
                    "f1_score": stmt.excluded.f1_score,
                    "fpr": stmt.excluded.fpr,
                    "loss": stmt.excluded.loss,
                    "selected_features": stmt.excluded.selected_features,
                    "confusion_matrix": stmt.excluded.confusion_matrix,
                    "is_active": stmt.excluded.is_active,
                },
            )
            session.execute(stmt)

    logger.info(f"Registered {len(registered_records)} models in model_registry.")
    return {
        "status": "success",
        "registered_count": len(registered_records),
        "models": [r["model_name"] for r in registered_records],
        "active_models": [r["model_name"] for r in registered_records if r["is_active"]],
        "inactive_models": [r["model_name"] for r in registered_records if not r["is_active"]],
    }


def ingest_classical_ml_predictions(
    run_id: str,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR,
    version_tag: str = "baseline",
    models_dir: Optional[Path] = None,
    batch_size: int = 100,
) -> Dict[str, Any]:
    """
    Ingest authentic classical ML predictions from CSV into the ml_predictions table.
    
    Preconditions:
      - CSV exists and its SHA-256 matches the recorded simulation_artifacts hash.
      - Exactly 1,192 rows, 149 timesteps, 8 nodes, 0 duplicates.
      - Eligible models (RandomForest, SVM, MLP) exist in model_registry and are marked is_active=True.
      - Physical model artifacts exist on disk and match their registered SHA-256 hashes.
      - confidence is stored as NULL.
      - Atomic transaction: rolls back all writes on error.
      - Idempotency: on_conflict_do_update on (simulation_run_id, model_id, time_sec, node_id).
    """
    logger.info(f"Starting Phase B3.3 classical ML prediction ingestion for run {run_id}")

    csv_path = Path(dynamic_dir) / f"run_{run_id}_classical_ml_predictions.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Classical ML prediction CSV missing for run {run_id}: {csv_path}")

    actual_csv_hash = compute_file_sha256(csv_path)

    # Database resolution, verification, and atomic insertion in a single transaction
    with get_write_session() as session:
        # 1. Resolve simulation run
        run = session.query(SimulationRun).filter_by(run_id=run_id).first()
        if not run:
            raise ValueError(f"SimulationRun record not found for run_id: {run_id}")
        run_db_id = run.id

        # 2. Verify artifact hash against simulation_artifacts if record exists
        art = (
            session.query(SimulationArtifact)
            .filter_by(simulation_run_id=run_db_id)
            .filter(SimulationArtifact.file_type.in_(["classical_ml_csv", "classical_ml_predictions"]))
            .first()
        )
        if art and art.file_hash_sha256 != actual_csv_hash:
            raise ValueError(
                f"Prediction CSV hash mismatch for run {run_id}: "
                f"artifact record has {art.file_hash_sha256}, physical file has {actual_csv_hash}"
            )

        # 3. Resolve eligible models (RandomForest, SVM, MLP)
        eligible_models = ["RandomForest", "SVM", "MLP"]
        model_id_map: Dict[str, int] = {}
        m_base_dir = Path(models_dir) if models_dir is not None else BASELINE_MODELS_DIR

        for m_name in eligible_models:
            reg = (
                session.query(ModelRegistry)
                .filter_by(model_name=m_name, version_tag=version_tag, model_type="classical_ml")
                .first()
            )
            if not reg:
                raise ValueError(
                    f"Eligible model '{m_name}' (version '{version_tag}') not registered in model_registry"
                )
            if not reg.is_active:
                raise ValueError(f"Model '{m_name}' is marked inactive in model_registry")

            # Verify physical artifact file on disk
            art_file = m_base_dir / f"{m_name}.pkl"
            if not art_file.exists():
                raise FileNotFoundError(f"Model artifact file missing on disk: {art_file}")
            art_hash = compute_file_sha256(art_file)
            if art_hash != reg.file_hash_sha256:
                raise ValueError(
                    f"Model artifact hash mismatch for '{m_name}': "
                    f"registry has {reg.file_hash_sha256}, disk has {art_hash}"
                )

            model_id_map[m_name] = reg.id

        # 4. Validate and parse CSV into memory before database write
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])

            req_cols = [
                "time", "node", "rx", "control_message_frequency", "label",
                "RandomForest_pred", "SVM_pred", "MLP_pred",
            ]
            for c in req_cols:
                if c not in fieldnames:
                    raise ValueError(f"Required column '{c}' missing from prediction CSV {csv_path.name}")

            rows = []
            unique_times = set()
            unique_nodes = set()
            seen_time_node = set()

            for row_idx, r in enumerate(reader):
                try:
                    t_val = float(r["time"])
                    n_val = int(r["node"])
                    rx_val = float(r["rx"])
                    cf_val = float(r["control_message_frequency"])
                    lbl_val = int(r["label"])
                    rf_val = int(r["RandomForest_pred"])
                    svm_val = int(r["SVM_pred"])
                    mlp_val = int(r["MLP_pred"])
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid numeric data at row {row_idx} in {csv_path.name}: {e}")

                # Bounds and domain checks
                if t_val < 0:
                    raise ValueError(f"Negative time {t_val} at row {row_idx}")
                if n_val < 0 or n_val > 7:
                    raise ValueError(f"Node ID {n_val} out of valid range [0, 7] at row {row_idx}")
                if rx_val < 0:
                    raise ValueError(f"Negative rx {rx_val} at row {row_idx}")
                if cf_val < 0:
                    raise ValueError(f"Negative control_freq {cf_val} at row {row_idx}")
                if lbl_val not in (0, 1):
                    raise ValueError(f"Non-binary ground truth label {lbl_val} at row {row_idx}")
                if rf_val not in (0, 1):
                    raise ValueError(f"Non-binary RandomForest_pred {rf_val} at row {row_idx}")
                if svm_val not in (0, 1):
                    raise ValueError(f"Non-binary SVM_pred {svm_val} at row {row_idx}")
                if mlp_val not in (0, 1):
                    raise ValueError(f"Non-binary MLP_pred {mlp_val} at row {row_idx}")

                pair = (t_val, n_val)
                if pair in seen_time_node:
                    raise ValueError(f"Duplicate (time, node) pair {pair} at row {row_idx}")
                seen_time_node.add(pair)
                unique_times.add(t_val)
                unique_nodes.add(n_val)

                rows.append({
                    "time": t_val,
                    "node": n_val,
                    "rx": rx_val,
                    "control_freq": cf_val,
                    "label": lbl_val,
                    "RandomForest_pred": rf_val,
                    "SVM_pred": svm_val,
                    "MLP_pred": mlp_val,
                })

        # Global structural validation
        if len(rows) != 1192:
            raise ValueError(f"Expected exactly 1192 rows in {csv_path.name}, got {len(rows)}")
        if len(unique_times) != 149:
            raise ValueError(f"Expected exactly 149 unique timesteps, got {len(unique_times)}")
        if len(unique_nodes) != 8:
            raise ValueError(f"Expected exactly 8 unique nodes, got {len(unique_nodes)}")

        # 4. Prepare batch records
        all_predictions = []
        for m_name in eligible_models:
            m_id = model_id_map[m_name]
            pred_key = f"{m_name}_pred"
            for r in rows:
                all_predictions.append({
                    "simulation_run_id": run_db_id,
                    "model_id": m_id,
                    "time_sec": r["time"],
                    "node_id": r["node"],
                    "rx_packets": r["rx"],
                    "control_freq": r["control_freq"],
                    "ground_truth_label": r["label"],
                    "predicted_label": r[pred_key],
                    "confidence": None,
                })

        # 5. Execute batch upsert
        for i in range(0, len(all_predictions), batch_size):
            chunk = all_predictions[i : i + batch_size]
            stmt = sqlite_insert(MLPrediction).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["simulation_run_id", "model_id", "time_sec", "node_id"],
                set_={
                    "rx_packets": stmt.excluded.rx_packets,
                    "control_freq": stmt.excluded.control_freq,
                    "ground_truth_label": stmt.excluded.ground_truth_label,
                    "predicted_label": stmt.excluded.predicted_label,
                    "confidence": stmt.excluded.confidence,
                },
            )
            session.execute(stmt)

    logger.info(
        f"Successfully ingested {len(all_predictions)} classical ML predictions for run {run_id} "
        f"({len(rows)} rows x {len(eligible_models)} models)."
    )
    return {
        "status": "success",
        "run_id": run_id,
        "simulation_run_id": run_db_id,
        "total_records": len(all_predictions),
        "per_model_counts": {m: len(rows) for m in eligible_models},
    }


def ingest_trust_evaluations(
    run_id: str,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR,
    batch_size: int = 200,
) -> Dict[str, Any]:
    """
    Ingest authentic LSTM trust evaluation predictions from CSV into the trust_evaluations table.
    
    Preconditions and Invariants:
      - CSV exists at dynamic_dir / f"run_{run_id}_lstm_pred.csv".
      - CSV SHA-256 matches recorded simulation_artifacts hash (file_type='lstm_pred_csv').
      - Required columns: time, node, score, is_malicious.
      - Exactly 1,160 rows, 145 unique timesteps, 8 unique nodes, 0 duplicate (time, node) pairs.
      - All values are finite and within domain bounds:
          time >= 0
          0 <= node <= 7
          0.0 <= score <= 1.0
          is_malicious in (0, 1)
          is_malicious == (1 if score < 0.5 else 0)
      - Exact timestamp key semantics: (time_sec, node_id) without rounding.
      - Conflict-safe resolution against existing DB records:
          Identical records (within tolerance 1e-5 for floats, exact for ints/strings): NO-OP.
          Conflicting records: abort transaction immediately, persist 0 rows, raise ValueError.
      - Inferred action semantics:
          'Blacklisted' if is_malicious == 1 else 'None'
      - Atomic multi-batch insertion:
          All validations and conflict checks complete before any DB write.
          Inserts in chunks of batch_size within single uncommitted write transaction.
          Zero intermediate commits; rollback all on any failure.
    """
    logger.info(f"Starting Phase B4.3 LSTM trust evaluation ingestion for run {run_id}")

    csv_path = Path(dynamic_dir) / f"run_{run_id}_lstm_pred.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"LSTM prediction CSV missing for run {run_id}: {csv_path}")

    actual_csv_hash = compute_file_sha256(csv_path)

    # Database resolution, verification, conflict-audit, and atomic insertion in a single transaction
    with get_write_session() as session:
        # 1. Resolve simulation run dynamically
        run = session.query(SimulationRun).filter_by(run_id=run_id).first()
        if not run:
            raise ValueError(f"SimulationRun record not found for run_id: {run_id}")
        run_db_id = run.id

        # 2. Verify recorded artifact hash parity
        artifact = (
            session.query(SimulationArtifact)
            .filter_by(simulation_run_id=run_db_id, file_type="lstm_pred_csv")
            .first()
        )
        if not artifact:
            raise ValueError(f"SimulationArtifact 'lstm_pred_csv' not found for run {run_id}")
        if artifact.file_hash_sha256 != actual_csv_hash:
            raise ValueError(
                f"SHA-256 mismatch for {csv_path.name}: catalog={artifact.file_hash_sha256}, actual={actual_csv_hash}"
            )

        # 3. Parse and validate CSV strictly in memory before any database write
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            req_cols = ["time", "node", "score", "is_malicious"]
            for c in req_cols:
                if c not in fieldnames:
                    raise ValueError(f"Required column '{c}' missing from LSTM prediction CSV {csv_path.name}")

            rows = []
            unique_times = set()
            unique_nodes = set()
            seen_time_node = set()

            for row_idx, r in enumerate(reader):
                t_raw = r.get("time")
                n_raw = r.get("node")
                s_raw = r.get("score")
                m_raw = r.get("is_malicious")

                if t_raw is None or n_raw is None or s_raw is None or m_raw is None:
                    raise ValueError(f"Null or missing value at row {row_idx} in {csv_path.name}")

                try:
                    t_val = float(t_raw)
                    n_val = int(n_raw)
                    s_val = float(s_raw)
                    m_val = int(m_raw)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid numeric data at row {row_idx} in {csv_path.name}: {e}")

                # Check finite
                if math.isnan(t_val) or math.isinf(t_val):
                    raise ValueError(f"Non-finite timestamp at row {row_idx}: {t_val}")
                if math.isnan(s_val) or math.isinf(s_val):
                    raise ValueError(f"Non-finite trust score at row {row_idx}: {s_val}")

                # Bounds and domain checks
                if t_val < 0.0:
                    raise ValueError(f"Negative time {t_val} at row {row_idx}")
                if n_val < 0 or n_val > 7:
                    raise ValueError(f"Node ID {n_val} out of valid range [0, 7] at row {row_idx}")
                if s_val < 0.0 or s_val > 1.0:
                    raise ValueError(f"Trust score {s_val} out of range [0.0, 1.0] at row {row_idx}")
                if m_val not in (0, 1):
                    raise ValueError(f"Non-binary is_malicious {m_val} at row {row_idx}")

                # Consistency with decision threshold 0.5
                expected_mal = 1 if s_val < 0.5 else 0
                if m_val != expected_mal:
                    raise ValueError(
                        f"Classification inconsistency at row {row_idx}: score={s_val} "
                        f"implies is_malicious={expected_mal}, got {m_val}"
                    )

                # Check duplicate (time, node)
                pair = (t_val, n_val)
                if pair in seen_time_node:
                    raise ValueError(f"Duplicate (time, node) pair {pair} at row {row_idx}")
                seen_time_node.add(pair)
                unique_times.add(t_val)
                unique_nodes.add(n_val)

                inferred_action = "Blacklisted" if m_val == 1 else "None"
                rows.append({
                    "time_sec": t_val,
                    "node_id": n_val,
                    "trust_score": s_val,
                    "threshold": 0.5,
                    "is_malicious": m_val,
                    "inferred_action": inferred_action,
                })

        # Global structural validation
        # Base LSTM predictions contain 1160 rows across 145 timesteps for 8 nodes.
        # When malicious nodes are present, pass 2 appends routing exclusion overrides (time=0.0)
        # resulting in 1160 + num_malicious rows and 145 or 146 unique timesteps.
        expected_base_rows = 1160
        expected_max_rows = 1160 + (run.num_malicious or 0)
        if len(rows) < expected_base_rows or len(rows) > expected_max_rows:
            raise ValueError(
                f"Expected between {expected_base_rows} and {expected_max_rows} rows in {csv_path.name}, got {len(rows)}"
            )
        if len(unique_times) not in (145, 146):
            raise ValueError(f"Expected 145 or 146 unique timesteps, got {len(unique_times)}")
        if len(unique_nodes) != 8:
            raise ValueError(f"Expected exactly 8 unique nodes, got {len(unique_nodes)}")

        # 4. Query existing records for this run to enforce conflict-safety
        existing_records = (
            session.query(TrustEvaluation)
            .filter_by(simulation_run_id=run_db_id)
            .all()
        )
        existing_map = {
            (r.time_sec, r.node_id): r
            for r in existing_records
        }

        conflicts = []
        to_insert = []
        already_existing_count = 0

        for r in rows:
            key = (r["time_sec"], r["node_id"])
            if key in existing_map:
                existing = existing_map[key]

                score_match = math.isclose(existing.trust_score, r["trust_score"], abs_tol=1e-5)
                thresh_match = math.isclose(existing.threshold, r["threshold"], abs_tol=1e-5)
                mal_match = (existing.is_malicious == r["is_malicious"])
                act_match = (existing.inferred_action == r["inferred_action"])

                if score_match and thresh_match and mal_match and act_match:
                    already_existing_count += 1
                else:
                    conflicts.append({
                        "key": {"simulation_run_id": run_db_id, "time_sec": r["time_sec"], "node_id": r["node_id"]},
                        "mismatches": {
                            "trust_score": {"existing": existing.trust_score, "incoming": r["trust_score"]} if not score_match else None,
                            "threshold": {"existing": existing.threshold, "incoming": r["threshold"]} if not thresh_match else None,
                            "is_malicious": {"existing": existing.is_malicious, "incoming": r["is_malicious"]} if not mal_match else None,
                            "inferred_action": {"existing": existing.inferred_action, "incoming": r["inferred_action"]} if not act_match else None,
                        }
                    })
            else:
                row_dict = dict(r)
                row_dict["simulation_run_id"] = run_db_id
                to_insert.append(row_dict)

        # 5. Abort on any conflict
        if conflicts:
            raise ValueError(
                f"Ingestion rejected for run '{run_id}': {len(conflicts)} conflicting records detected in "
                f"'trust_evaluations'. Overwriting existing data is strictly forbidden. "
                f"First conflict: {conflicts[0]}"
            )

        # 6. Atomic multi-batch insertion (single transaction, zero intermediate commits)
        if to_insert:
            for i in range(0, len(to_insert), batch_size):
                chunk = to_insert[i : i + batch_size]
                session.bulk_insert_mappings(TrustEvaluation, chunk)

    logger.info(
        f"Successfully processed LSTM trust evaluations for run {run_id}: "
        f"{len(to_insert)} inserted, {already_existing_count} already existing (NO-OP)."
    )
    return {
        "status": "success",
        "run_id": run_id,
        "simulation_run_id": run_db_id,
        "total_source_records": len(rows),
        "inserted_count": len(to_insert),
        "already_existing_count": already_existing_count,
    }


def _ingest_routing_records_with_session(
    session: Session,
    run_id: str,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR,
    routing_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Internal implementation of routing record ingestion operating within an active Session.
    """
    # 1. Resolve simulation run dynamically using run identifier
    run = session.query(SimulationRun).filter_by(run_id=run_id).first()
    if not run:
        raise ValueError(f"Simulation run '{run_id}' not found in simulation_runs database table.")
    run_db_id = run.id

    # 2. Resolve source file path
    json_path = routing_file or (dynamic_dir / f"run_{run_id}_routing.json")
    if not json_path.exists():
        raise FileNotFoundError(f"Routing JSON file not found at: {json_path}")

    # 3. Verify source file hash and registered artifact
    computed_hash = compute_file_sha256(json_path)

    artifact = (
        session.query(SimulationArtifact)
        .filter_by(simulation_run_id=run_db_id, file_type="routing_json_p2")
        .first()
    )
    if not artifact:
        raise ValueError(
            f"No registered 'routing_json_p2' artifact found in simulation_artifacts for run '{run_id}' (ID: {run_db_id})."
        )
    if artifact.file_hash_sha256 != computed_hash:
        raise ValueError(
            f"Artifact SHA-256 mismatch for run '{run_id}': on-disk hash is '{computed_hash}', "
            f"but registered artifact (ID: {artifact.id}) hash is '{artifact.file_hash_sha256}'."
        )

    # 4. Parse and validate JSON
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"Malformed JSON in routing file '{json_path.name}': {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Routing file root must be a JSON object, got {type(data).__name__}")

    # Required JSON keys
    required_keys = [
        "run_id",
        "source_node",
        "destination_node",
        "hop_count",
        "route_available",
        "destination_reached",
        "hops",
    ]
    missing_keys = [k for k in required_keys if k not in data]
    if missing_keys:
        raise ValueError(f"Routing JSON missing required keys: {missing_keys}")

    # Validate run_id
    if data["run_id"] != run_id:
        raise ValueError(
            f"Routing JSON run_id '{data['run_id']}' does not match requested run_id '{run_id}'"
        )

    # Validate source and destination node IDs
    source_node = data["source_node"]
    dest_node = data["destination_node"]
    if not isinstance(source_node, int) or isinstance(source_node, bool):
        raise ValueError(f"source_node must be integer, got {type(source_node).__name__}: {source_node}")
    if not isinstance(dest_node, int) or isinstance(dest_node, bool):
        raise ValueError(f"destination_node must be integer, got {type(dest_node).__name__}: {dest_node}")

    num_nodes = run.num_nodes
    if source_node < 0 or source_node >= num_nodes:
        raise ValueError(f"source_node {source_node} out of valid range [0, {num_nodes - 1}]")
    if dest_node < 0 or dest_node >= num_nodes:
        raise ValueError(f"destination_node {dest_node} out of valid range [0, {num_nodes - 1}]")

    # Validate boolean fields
    route_available = data.get("route_available")
    if not isinstance(route_available, bool):
        raise ValueError(f"route_available must be a boolean, got {type(route_available).__name__}")
    dest_reached = data.get("destination_reached", False)
    if not isinstance(dest_reached, bool):
        raise ValueError(f"destination_reached must be a boolean, got {type(dest_reached).__name__}")

    # Validate hops list
    hops = data.get("hops")
    if not isinstance(hops, list):
        raise ValueError(f"hops must be a list, got {type(hops).__name__}")

    if route_available:
        if len(hops) == 0:
            raise ValueError("hops must be a non-empty list when route_available is True")

        for idx, h in enumerate(hops):
            if not isinstance(h, dict):
                raise ValueError(f"Hop at index {idx} must be a dictionary, got {type(h).__name__}")
            for k in ("node_id", "time", "ip"):
                if k not in h:
                    raise ValueError(f"Hop at index {idx} missing required key '{k}'")

            nid = h["node_id"]
            if not isinstance(nid, int) or isinstance(nid, bool):
                raise ValueError(f"Hop {idx} node_id must be integer, got {type(nid).__name__}")
            if nid < 0 or nid >= num_nodes:
                raise ValueError(f"Hop {idx} node_id {nid} out of bounds [0, {num_nodes - 1}]")

            t = h["time"]
            if not isinstance(t, (int, float)) or isinstance(t, bool):
                raise ValueError(f"Hop {idx} time must be numeric, got {type(t).__name__}")
            if math.isnan(t) or math.isinf(t) or t < 0:
                raise ValueError(f"Hop {idx} time must be a finite non-negative number, got {t}")

            ip = h["ip"]
            if not isinstance(ip, str) or not ip.strip():
                raise ValueError(f"Hop {idx} ip must be non-empty string, got {ip}")

        # First hop must equal source node
        if hops[0]["node_id"] != source_node:
            raise ValueError(
                f"First hop node_id {hops[0]['node_id']} does not match source_node {source_node}"
            )

        # Last hop must equal dest node if destination_reached is True
        if dest_reached and hops[-1]["node_id"] != dest_node:
            raise ValueError(
                f"Last hop node_id {hops[-1]['node_id']} does not match destination_node {dest_node} "
                f"when destination_reached is True"
            )

        # Validate hop_count == len(hops) - 1
        hop_count = data.get("hop_count")
        if not isinstance(hop_count, int) or isinstance(hop_count, bool):
            raise ValueError(f"hop_count must be integer, got {type(hop_count).__name__}")
        if hop_count != len(hops) - 1:
            raise ValueError(
                f"hop_count ({hop_count}) does not match len(hops) - 1 ({len(hops) - 1})"
            )
    else:
        # Route not available (e.g. black-hole isolation or unreachable destination)
        if dest_reached:
            raise ValueError("destination_reached cannot be True when route_available is False")
        hop_count = data.get("hop_count", 0)
        if not isinstance(hop_count, int) or isinstance(hop_count, bool):
            hop_count = 0

    # Resolve authoritative malicious nodes
    malicious_nodes_set = set()
    if run.num_malicious and run.num_malicious > 0:
        if run.ground_truth_malicious is None:
            raise ValueError(
                f"Cannot determine authoritative malicious nodes for run '{run_id}': "
                f"num_malicious={run.num_malicious} but ground_truth_malicious is None."
            )
        try:
            raw_gt = run.ground_truth_malicious
            parsed_gt = json.loads(raw_gt) if isinstance(raw_gt, str) else raw_gt
            if isinstance(parsed_gt, list):
                malicious_nodes_set = set(int(x) for x in parsed_gt)
            elif isinstance(parsed_gt, int):
                malicious_nodes_set = {parsed_gt}
            else:
                raise ValueError(f"Unexpected ground_truth_malicious type: {type(parsed_gt)}")
        except Exception as e:
            raise ValueError(f"Failed to parse ground_truth_malicious for run '{run_id}': {e}")

    # Compute has_malicious_node from actual hop sequence
    if hops:
        hop_node_ids = {h["node_id"] for h in hops}
        has_malicious = bool(hop_node_ids & malicious_nodes_set)
    else:
        has_malicious = False

    # Notes normalization
    raw_note = data.get("note")
    normalized_notes = raw_note.strip() if isinstance(raw_note, str) and raw_note.strip() else None

    # Serialized hops_json
    hops_json_str = json.dumps(hops)
    phase_val = "mitigated_pass2"

    # 5. Conflict-Safe Idempotency check on unique key: (simulation_run_id, phase, source_node, dest_node)
    existing = (
        session.query(RoutingRecord)
        .filter_by(
            simulation_run_id=run_db_id,
            phase=phase_val,
            source_node=source_node,
            dest_node=dest_node,
        )
        .first()
    )

    if existing:
        mismatches = {}
        if existing.hop_count != hop_count:
            mismatches["hop_count"] = {"existing": existing.hop_count, "incoming": hop_count}
        if existing.route_available != route_available:
            mismatches["route_available"] = {"existing": existing.route_available, "incoming": route_available}
        if existing.destination_reached != dest_reached:
            mismatches["destination_reached"] = {"existing": existing.destination_reached, "incoming": dest_reached}
        if existing.has_malicious_node != has_malicious:
            mismatches["has_malicious_node"] = {"existing": existing.has_malicious_node, "incoming": has_malicious}

        # Compare hops as parsed JSON objects to avoid whitespace/ordering false conflicts
        try:
            existing_hops = json.loads(existing.hops_json) if isinstance(existing.hops_json, str) else existing.hops_json
        except Exception:
            existing_hops = None
        if existing_hops != hops:
            mismatches["hops_json"] = {"existing": existing_hops, "incoming": hops}

        existing_norm_notes = existing.notes.strip() if isinstance(existing.notes, str) and existing.notes.strip() else None
        if existing_norm_notes != normalized_notes:
            mismatches["notes"] = {"existing": existing.notes, "incoming": raw_note}

        if mismatches:
            raise ValueError(
                f"Conflicting routing record for run '{run_id}' (phase='{phase_val}', source={source_node}, dest={dest_node}). "
                f"Overwriting existing data is strictly forbidden. Mismatches: {mismatches}"
            )

        logger.info(
            f"Routing record for run {run_id} ({phase_val}, source={source_node}, dest={dest_node}) "
            f"already exists with identical data. NO-OP."
        )
        return {
            "status": "ALREADY_INGESTED",
            "run_id": run_id,
            "simulation_run_id": run_db_id,
            "inserted": 0,
            "existing": 1,
            "routing_record_id": existing.id,
            "phase": phase_val,
        }

    # 6. Insert single verified Pass 2 record
    new_record = RoutingRecord(
        simulation_run_id=run_db_id,
        phase=phase_val,
        source_node=source_node,
        dest_node=dest_node,
        hop_count=hop_count,
        route_available=route_available,
        destination_reached=dest_reached,
        hops_json=hops_json_str,
        has_malicious_node=has_malicious,
        notes=normalized_notes,
    )
    session.add(new_record)
    session.flush()

    logger.info(
        f"Successfully ingested routing record ID {new_record.id} for run {run_id} ({phase_val})."
    )
    return {
        "status": "success",
        "run_id": run_id,
        "simulation_run_id": run_db_id,
        "inserted": 1,
        "existing": 0,
        "routing_record_id": new_record.id,
        "phase": phase_val,
    }


def ingest_routing_records(
    run_id: Any,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR,
    routing_file: Optional[Path] = None,
    db: Optional[Session] = None,
    session: Optional[Session] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Ingest verified Pass 2 routing summary into SQLite `routing_records`.
    Enforces strict conflict-safe idempotency and schema validation.
    
    Supports:
      - ingest_routing_records(run_id, dynamic_dir=...)
      - ingest_routing_records(run_id, db=session)
      - ingest_routing_records(session, run_id=run_id)
    """
    active_session = session or db
    actual_run_id = run_id

    # Handle polymorphic signature if session is passed as first argument
    if hasattr(run_id, "execute") and hasattr(run_id, "query"):
        active_session = run_id
        actual_run_id = kwargs.get("simulation_run_id") or kwargs.get("run_id")
        if not actual_run_id and isinstance(dynamic_dir, str):
            actual_run_id = dynamic_dir
            dynamic_dir = DYNAMIC_RESULTS_DIR
    elif "simulation_run_id" in kwargs and not actual_run_id:
        actual_run_id = kwargs["simulation_run_id"]

    if not actual_run_id or not isinstance(actual_run_id, str):
        raise ValueError(f"Invalid or missing run_id: {actual_run_id}")

    if active_session is not None:
        return _ingest_routing_records_with_session(
            session=active_session,
            run_id=actual_run_id,
            dynamic_dir=dynamic_dir,
            routing_file=routing_file,
        )
    else:
        with get_write_session() as managed_session:
            return _ingest_routing_records_with_session(
                session=managed_session,
                run_id=actual_run_id,
                dynamic_dir=dynamic_dir,
                routing_file=routing_file,
            )


HISTORICAL_PILOT_RUN_ID = "20261111_225145_8e3c4f7c_8nodes_attack2_4"


def ingest_prevention_events(
    run_id: str,
    dynamic_dir: Path = DYNAMIC_RESULTS_DIR,
    events_file: Optional[Path] = None,
    session: Optional[Session] = None,
    db: Optional[Session] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Ingest verified NS-3 prevention event records into SQLite `prevention_events`
    and `artifact_ingestion_ledger` under strict transaction atomicity, single-read byte snapshot
    hashing (TOCTOU protection), and historical pilot invariance.
    """
    actual_run_id = run_id
    if hasattr(run_id, "execute") and hasattr(run_id, "query"):
        session = run_id
        actual_run_id = kwargs.get("simulation_run_id") or kwargs.get("run_id")
    elif "simulation_run_id" in kwargs and not actual_run_id:
        actual_run_id = kwargs["simulation_run_id"]

    if not actual_run_id or not isinstance(actual_run_id, str):
        raise ValueError(f"Invalid or missing run_id: {actual_run_id}")

    # 1. Resolve run from database
    with get_write_session() as s_check:
        run = s_check.query(SimulationRun).filter_by(run_id=actual_run_id).first()
        if not run:
            raise ValueError(f"SimulationRun record not found for run_id: {actual_run_id}")
        run_db_id = run.id

        # 2. Check catalog entry in simulation_artifacts
        art = (
            s_check.query(SimulationArtifact)
            .filter_by(simulation_run_id=run_db_id, file_type="prevention_events_json")
            .first()
        )

    # 3. Historical Pilot Protection Gate
    if actual_run_id == HISTORICAL_PILOT_RUN_ID and not art:
        logger.info(
            f"Historical pilot run {actual_run_id} safely preserved with zero prevention events (no authentic artifact)."
        )
        return {
            "status": "HISTORICAL_PILOT_PRESERVED",
            "run_id": actual_run_id,
            "simulation_run_id": run_db_id,
            "inserted": 0,
            "existing": 0,
            "message": "Historical pilot run safely preserved with zero prevention events.",
        }

    # 4. Resolve file path
    artifact_path = Path(events_file) if events_file else Path(dynamic_dir) / f"run_{actual_run_id}_prevention_events.json"

    # If artifact catalog entry is missing or file does not physically exist on disk -> SKIPPED_NO_ARTIFACT
    if not art or not artifact_path.exists():
        with get_write_session() as s_skip:
            max_att = (
                s_skip.query(func.max(ArtifactIngestionLedger.attempt_number))
                .filter_by(simulation_run_id=run_db_id, artifact_type="prevention_events_json")
                .scalar()
                or 0
            )
            skip_entry = ArtifactIngestionLedger(
                simulation_run_id=run_db_id,
                artifact_type="prevention_events_json",
                file_hash_sha256=None,
                attempt_number=max_att + 1,
                ingestion_status="SKIPPED_NO_ARTIFACT",
                rows_inserted=0,
                error_message="Artifact missing from disk or not registered in simulation_artifacts catalog.",
            )
            s_skip.add(skip_entry)

        logger.info(f"Prevention event artifact missing for run {actual_run_id}. Recorded SKIPPED_NO_ARTIFACT.")
        return {
            "status": "SKIPPED_NO_ARTIFACT",
            "run_id": actual_run_id,
            "simulation_run_id": run_db_id,
            "inserted": 0,
            "existing": 0,
        }

    # 5. Read single-read byte snapshot (TOCTOU protection)
    raw_bytes = artifact_path.read_bytes()
    verified_snapshot_hash = hashlib.sha256(raw_bytes).hexdigest()

    # 6. Verify snapshot hash matches registered catalog hash
    if verified_snapshot_hash != art.file_hash_sha256:
        err_msg = (
            f"Artifact hash mismatch for run {actual_run_id}: "
            f"catalog has {art.file_hash_sha256}, physical snapshot has {verified_snapshot_hash}"
        )
        with get_write_session() as s_fail:
            max_att = (
                s_fail.query(func.max(ArtifactIngestionLedger.attempt_number))
                .filter_by(simulation_run_id=run_db_id, artifact_type="prevention_events_json")
                .scalar()
                or 0
            )
            s_fail.add(
                ArtifactIngestionLedger(
                    simulation_run_id=run_db_id,
                    artifact_type="prevention_events_json",
                    file_hash_sha256=verified_snapshot_hash,
                    attempt_number=max_att + 1,
                    ingestion_status="FAILED",
                    rows_inserted=0,
                    error_message=err_msg,
                )
            )
        raise ValueError(err_msg)

    # 7. Parse JSON syntax from verified snapshot
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        err_msg = f"Invalid JSON syntax in prevention artifact for run {actual_run_id}: {e}"
        with get_write_session() as s_fail:
            max_att = (
                s_fail.query(func.max(ArtifactIngestionLedger.attempt_number))
                .filter_by(simulation_run_id=run_db_id, artifact_type="prevention_events_json")
                .scalar()
                or 0
            )
            s_fail.add(
                ArtifactIngestionLedger(
                    simulation_run_id=run_db_id,
                    artifact_type="prevention_events_json",
                    file_hash_sha256=verified_snapshot_hash,
                    attempt_number=max_att + 1,
                    ingestion_status="FAILED",
                    rows_inserted=0,
                    error_message=err_msg,
                )
            )
        raise ValueError(err_msg)

    events_list = data.get("events", [])
    if not isinstance(events_list, list):
        raise ValueError(f"'events' key must be a list in prevention artifact for run {actual_run_id}")

    # 8. Atomic Transaction Execution
    next_attempt = 1
    with get_write_session() as session:
        session.execute(text("BEGIN IMMEDIATE"))

        # Re-query ledger inside write lock
        latest_terminal = (
            session.query(ArtifactIngestionLedger)
            .filter_by(simulation_run_id=run_db_id, artifact_type="prevention_events_json")
            .filter(ArtifactIngestionLedger.ingestion_status.in_(["SUCCESS", "AUTHENTIC_EMPTY"]))
            .order_by(ArtifactIngestionLedger.attempt_number.desc())
            .first()
        )

        if latest_terminal:
            if latest_terminal.file_hash_sha256 == verified_snapshot_hash:
                session.rollback()
                return {
                    "status": "ALREADY_INGESTED",
                    "run_id": actual_run_id,
                    "simulation_run_id": run_db_id,
                    "inserted": 0,
                    "existing": latest_terminal.rows_inserted,
                    "ledger_id": latest_terminal.id,
                }
            else:
                session.rollback()
                raise ValueError(
                    f"Refusing re-ingestion with altered hash for run {actual_run_id}. "
                    f"Prior: {latest_terminal.file_hash_sha256}, New: {verified_snapshot_hash}"
                )

        # Anomaly Recovery Check: Existing rows without ledger
        existing_events = (
            session.query(PreventionEvent)
            .filter_by(simulation_run_id=run_db_id)
            .order_by(PreventionEvent.sequence.asc())
            .all()
        )

        max_att = (
            session.query(func.max(ArtifactIngestionLedger.attempt_number))
            .filter_by(simulation_run_id=run_db_id, artifact_type="prevention_events_json")
            .scalar()
            or 0
        )
        next_attempt = max_att + 1

        if existing_events:
            is_exact_match = True
            if len(existing_events) != len(events_list):
                is_exact_match = False
            else:
                for db_ev, art_ev in zip(existing_events, events_list):
                    if (
                        db_ev.sequence != art_ev.get("sequence")
                        or abs(db_ev.time_sec - float(art_ev.get("time_sec", 0))) > 1e-4
                        or db_ev.node_id != art_ev.get("node_id")
                        or db_ev.action_type != art_ev.get("action_type")
                        or db_ev.execution_status != art_ev.get("execution_status")
                        or db_ev.trigger_source != art_ev.get("trigger_source")
                    ):
                        is_exact_match = False
                        break

            if is_exact_match:
                ledger_entry = ArtifactIngestionLedger(
                    simulation_run_id=run_db_id,
                    artifact_type="prevention_events_json",
                    file_hash_sha256=verified_snapshot_hash,
                    attempt_number=next_attempt,
                    ingestion_status="SUCCESS" if len(existing_events) > 0 else "AUTHENTIC_EMPTY",
                    rows_inserted=len(existing_events),
                    error_message="Backfilled ledger entry for verified pre-existing event rows.",
                )
                session.add(ledger_entry)
                session.flush()
                return {
                    "status": "BACKFILLED_LEDGER",
                    "run_id": actual_run_id,
                    "simulation_run_id": run_db_id,
                    "inserted": 0,
                    "existing": len(existing_events),
                }
            else:
                session.rollback()
                raise IntegrityError(
                    f"Conflicting event rows exist in prevention_events for run {actual_run_id} without a ledger record. "
                    "Overwriting or replacing authentic data is strictly forbidden.",
                    params=None,
                    orig=None,
                )

        # Validate sequence ordering and supported enums
        expected_seq = 1
        for ev in events_list:
            seq = ev.get("sequence")
            if seq != expected_seq:
                session.rollback()
                raise ValueError(
                    f"Invalid sequence gap in events for run {actual_run_id}: expected {expected_seq}, got {seq}"
                )
            expected_seq += 1

            act = ev.get("action_type")
            if act not in ("INTERFACE_DOWN", "AODV_BLACKLIST", "RESTORE"):
                session.rollback()
                raise ValueError(f"Unsupported action_type '{act}' in run {actual_run_id}")
            if act == "RESTORE":
                session.rollback()
                raise ValueError(f"Action 'RESTORE' is reserved and rejected in current pipeline.")

            st = ev.get("execution_status")
            if st not in ("SUCCESS", "FAILED", "DUPLICATE_IGNORED", "UNVERIFIED"):
                session.rollback()
                raise ValueError(f"Unsupported execution_status '{st}' in run {actual_run_id}")

            trig = ev.get("trigger_source")
            if trig not in ("LSTM_PREDICTION", "STATIC_EXCLUSION"):
                session.rollback()
                raise ValueError(f"Unsupported trigger_source '{trig}' in run {actual_run_id}")

            t_sec = float(ev.get("time_sec", 0))
            if not math.isfinite(t_sec):
                session.rollback()
                raise ValueError(f"Non-finite time_sec in event for run {actual_run_id}")

            p_ev = PreventionEvent(
                simulation_run_id=run_db_id,
                sequence=seq,
                time_sec=t_sec,
                node_id=int(ev["node_id"]),
                action_type=act,
                execution_status=st,
                trigger_source=trig,
                details=ev.get("details"),
                error_message=ev.get("error_message"),
            )
            session.add(p_ev)

        term_status = "AUTHENTIC_EMPTY" if len(events_list) == 0 else "SUCCESS"
        ledger_entry = ArtifactIngestionLedger(
            simulation_run_id=run_db_id,
            artifact_type="prevention_events_json",
            file_hash_sha256=verified_snapshot_hash,
            attempt_number=next_attempt,
            ingestion_status=term_status,
            rows_inserted=len(events_list),
            error_message=None,
        )
        session.add(ledger_entry)
        session.flush()

        logger.info(
            f"Successfully ingested prevention events for run {actual_run_id}: "
            f"status={term_status}, events={len(events_list)}"
        )
        return {
            "status": term_status,
            "run_id": actual_run_id,
            "simulation_run_id": run_db_id,
            "inserted": len(events_list),
            "existing": 0,
        }




