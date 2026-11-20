from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import logging

import os
import json
from app.services.results_service import get_baseline_results, get_attack_results, get_main_flow
from app.services.simulation_runner import current_simulation, DYNAMIC_RESULTS_DIR
from app.services.trust_service import get_trust_scores, get_trust_prediction, get_ml_metrics, get_dynamic_trust_analysis
from app.services.routing_service import get_routing_path

logger = logging.getLogger("manet_backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup state recovery
    logger.info("[LIFESPAN] Backend starting up: initializing database state recovery...")
    try:
        from app.services.recovery_service import recover_backend_state
        res = recover_backend_state()
        logger.info(f"[LIFESPAN] Startup state recovery completed: {res}")
    except Exception as e:
        logger.error(f"[LIFESPAN] Startup recovery failed: {e}")
    yield
    # Shutdown safety
    logger.info("[LIFESPAN] Backend shutting down: executing shutdown safety hook...")
    try:
        from app.services.recovery_service import handle_backend_shutdown
        handle_backend_shutdown()
    except Exception as e:
        logger.error(f"[LIFESPAN] Shutdown safety hook failed: {e}")

app = FastAPI(title="MANET Trust-Aware Routing Backend", lifespan=lifespan)

# Configure CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class FlowMetrics(BaseModel):
    flow_id: int
    source_addr: str
    dest_addr: str
    tx_packets: int
    rx_packets: int
    lost_packets: int
    pdr_percent: float
    throughput_kbps: float
    mean_delay_ms: float

class EnergyMetrics(BaseModel):
    available: bool
    average_percentage: float
    nodes: List[Dict[str, Any]]

class ComparisonResponse(BaseModel):
    baseline: FlowMetrics
    attack: FlowMetrics
    maliciousNodes: List[int] | None = None
    pdr_drop_percent: float
    baseline_energy: EnergyMetrics | None = None
    current_run_energy: EnergyMetrics | None = None

# --- Endpoints ---

@app.get("/")
def read_root():
    return {
        "message": "MANET Backend is running",
        "status": "success"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "MANET Trust-Aware Routing Backend"
    }

from app.services.simulation_runner import run_simulation, current_simulation
from app.services.results_service import get_dynamic_results

class RunRequest(BaseModel):
    nNodes: int
    sourceNode: int = 0
    destinationNode: int | None = None
    attackEnabled: bool = False
    maliciousNodes: List[int] | None = None
    seed: int | None = None
    simArea: float | None = None
    demoTopology: bool = False
    simulationTime: float | None = 150.0
    packetRate: int | None = 2
    attackType: str | None = None

@app.post("/api/simulation/run")
def api_run_simulation(req: RunRequest):
    if req.nNodes < 2:
        raise HTTPException(status_code=400, detail="nNodes must be at least 2")
    
    malicious_nodes = req.maliciousNodes or []
    
    if req.attackEnabled:
        if not malicious_nodes:
            raise HTTPException(status_code=400, detail="attackEnabled is true but no malicious nodes provided")
        for node_id in malicious_nodes:
            if not isinstance(node_id, int):
                raise HTTPException(status_code=400, detail=f"maliciousNodes must contain integers, found: {node_id}")
            if node_id < 0 or node_id >= req.nNodes:
                raise HTTPException(status_code=400, detail=f"maliciousNode ID {node_id} must be between 0 and {req.nNodes - 1}")
        if len(set(malicious_nodes)) != len(malicious_nodes):
            raise HTTPException(status_code=400, detail="Duplicate malicious nodes are not allowed")
    else:
        malicious_nodes = []
    
    # ── Strict Parameter Validation & NS-3 Parity Enforcement ─────────────────
    # 1. simulationTime: must be > 0
    sim_time = req.simulationTime if req.simulationTime is not None else 150.0
    if not isinstance(sim_time, (int, float)) or sim_time <= 0:
        raise HTTPException(status_code=400, detail="simulationTime must be a positive number greater than 0")

    # 2. packetRate: must be an integer > 0
    pkt_rate = req.packetRate if req.packetRate is not None else 2
    if not isinstance(pkt_rate, int) or pkt_rate <= 0:
        raise HTTPException(status_code=400, detail="packetRate must be a positive integer greater than 0")

    # 3. attackType: strictly enforce genuinely implemented and executable attacks
    resolved_attack_type = "None"
    if req.attackEnabled:
        if req.attackType is None:
            resolved_attack_type = "Black Hole"
        else:
            norm_at = str(req.attackType).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
            if norm_at in ("blackhole",):
                resolved_attack_type = "Black Hole"
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported attackType '{req.attackType}'. "
                           f"Currently implemented and executable attack types: ['Black Hole']."
                )
    else:
        if req.attackType is not None:
            norm_at = str(req.attackType).strip().lower()
            if norm_at not in ("none", ""):
                raise HTTPException(
                    status_code=400,
                    detail=f"attackType '{req.attackType}' was specified but attackEnabled is False. "
                           f"Set attackEnabled to True or use attackType 'None'."
                )
        resolved_attack_type = "None"
    
    try:
        dest_node = req.destinationNode if req.destinationNode is not None else req.nNodes - 1
        if req.sourceNode < 0 or req.sourceNode >= req.nNodes:
             raise HTTPException(status_code=400, detail="Invalid source node")
        if dest_node < 0 or dest_node >= req.nNodes:
             raise HTTPException(status_code=400, detail="Invalid destination node")
        if req.sourceNode == dest_node:
             raise HTTPException(status_code=400, detail="Source and destination cannot be the same")
        
        # Verify database write ownership before initiating execution
        from app.services.recovery_service import is_database_owner
        if not is_database_owner():
            raise HTTPException(
                status_code=409,
                detail="This backend instance does not hold database write ownership. Another backend instance is active."
            )

        res = run_simulation(
            req.nNodes,
            maliciousNodes=malicious_nodes,
            attackEnabled=req.attackEnabled,
            seed=req.seed,
            simArea=req.simArea,
            demoTopology=req.demoTopology,
            sourceNode=req.sourceNode,
            destNode=dest_node,
            simulationTime=float(sim_time),
            packetRate=int(pkt_rate),
            attackType=resolved_attack_type,
        )
        return res
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/simulation/status")
def api_simulation_status():
    return {
        "status": current_simulation["status"],
        "run_id": current_simulation["run_id"],
        "nNodes": current_simulation["nNodes"],
        "sourceNode": current_simulation.get("sourceNode", 0),
        "destinationNode": current_simulation.get("destNode", current_simulation["nNodes"] - 1),
        "duration_seconds": current_simulation.get("duration_seconds"),
        "attackEnabled": current_simulation.get("attackEnabled", False),
        "maliciousNodes": current_simulation.get("maliciousNodes", []),
        "classical_ml": current_simulation.get("classical_ml", None),
        "persistence": current_simulation.get("persistence", None)
    }

@app.get("/api/simulation/runs")
def get_simulation_runs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None
):
    """
    Returns authentic historical simulation runs directly from the SQLite database.
    Supports pagination (limit: 1-200, offset >= 0) and validated status filtering ('running', 'completed', 'failed').
    """
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be greater than or equal to 0")

    norm_status = None
    if status is not None:
        norm_status = status.strip().lower()
        if norm_status not in ("running", "completed", "failed"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status filter '{status}'. Must be one of ['running', 'completed', 'failed']."
            )

    from database import get_read_session, SimulationRun

    try:
        with get_read_session() as session:
            query = session.query(SimulationRun)
            if norm_status:
                query = query.filter(SimulationRun.simulation_status == norm_status)

            total_count = query.count()
            runs = (
                query.order_by(SimulationRun.id.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            run_items = []
            for r in runs:
                dur = None
                if r.completed_at and r.started_at:
                    dur = round((r.completed_at - r.started_at).total_seconds(), 2)
                elif current_simulation.get("run_id") == r.run_id and current_simulation.get("duration_seconds") is not None:
                    dur = current_simulation.get("duration_seconds")

                run_items.append({
                    "run_id": r.run_id,
                    "protocol": r.protocol,
                    "num_nodes": r.num_nodes,
                    "num_malicious": r.num_malicious,
                    "attack_type": r.attack_type,
                    "packet_rate": r.packet_rate,
                    "simulation_time": r.simulation_time,
                    "simulation_status": r.simulation_status,
                    "persistence_status": r.persistence_status,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "duration_seconds": dur,
                })

            return {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "runs": run_items,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving simulation runs: {str(e)}")

@app.get("/api/simulation/summary")
def get_simulation_summary(run_id: Optional[str] = None):
    """
    Returns high-level simulation configuration summary.
    If run_id is supplied, queries genuine persisted parameters from SQLite.
    If run_id is omitted:
      - If an active simulation is completed in memory, returns active state.
      - If backend is idle, resolves the latest completed and persisted run from SQLite.
    """
    target_run_id = run_id

    # 1. Active simulation fast-path when run_id is omitted and memory state is completed
    if not target_run_id and current_simulation.get("status") == "completed":
        n = current_simulation["nNodes"]
        src = current_simulation.get("sourceNode", 0)
        dst = current_simulation.get("destNode", n - 1)
        return {
            "num_nodes": n,
            "area": "300x300m",
            "mobility": "RandomWaypoint",
            "routing": "AODV-based routing enhanced with a Geographic Request Zone mechanism",
            "duration_seconds": current_simulation.get("duration_seconds", 60),
            "sourceNode": src,
            "destinationNode": dst,
            "main_flow": f"Node {src} (10.1.1.{src + 1}) to Node {dst} (10.1.1.{dst + 1})",
            "attackEnabled": current_simulation.get("attackEnabled", False),
            "maliciousNodes": current_simulation.get("maliciousNodes", []),
        }

    from database import get_read_session, SimulationRun

    # 2. If run_id omitted and backend is idle, resolve latest eligible completed & persisted run from SQLite
    if not target_run_id:
        try:
            with get_read_session() as session:
                latest_run = (
                    session.query(SimulationRun)
                    .filter_by(simulation_status="completed", persistence_status="completed")
                    .order_by(SimulationRun.id.desc())
                    .first()
                )
                if latest_run:
                    target_run_id = latest_run.run_id
                else:
                    # Clean idle fallback if DB has no completed runs
                    n = current_simulation.get("nNodes", 8)
                    return {
                        "num_nodes": n,
                        "area": "300x300m",
                        "mobility": "RandomWaypoint",
                        "routing": "AODV-based routing enhanced with a Geographic Request Zone mechanism",
                        "duration_seconds": None,
                        "sourceNode": 0,
                        "destinationNode": n - 1,
                        "main_flow": f"Node 0 (10.1.1.1) to Node {n - 1} (10.1.1.{n})",
                        "attackEnabled": False,
                        "maliciousNodes": [],
                    }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error resolving latest simulation run: {str(e)}")

    # 3. Target run lookup from SQLite
    try:
        with get_read_session() as session:
            run = session.query(SimulationRun).filter_by(run_id=target_run_id).first()
            if not run:
                raise HTTPException(
                    status_code=404,
                    detail=f"Simulation run '{target_run_id}' not found."
                )

            n = run.num_nodes
            malicious_nodes = json.loads(run.ground_truth_malicious) if run.ground_truth_malicious else []
            attack_enabled = run.num_malicious > 0

            src = 0
            dst = n - 1
            if target_run_id == current_simulation.get("run_id"):
                src = current_simulation.get("sourceNode", 0)
                dst = current_simulation.get("destNode", n - 1)

            dur = None
            if run.completed_at and run.started_at:
                dur = round((run.completed_at - run.started_at).total_seconds(), 2)
            elif target_run_id == current_simulation.get("run_id"):
                dur = current_simulation.get("duration_seconds")

            return {
                "run_id": run.run_id,
                "num_nodes": n,
                "area": "300x300m",
                "mobility": "RandomWaypoint",
                "routing": "AODV-based routing enhanced with a Geographic Request Zone mechanism",
                "duration_seconds": dur,
                "sourceNode": src,
                "destinationNode": dst,
                "main_flow": f"Node {src} (10.1.1.{src + 1}) to Node {dst} (10.1.1.{dst + 1})",
                "attackEnabled": attack_enabled,
                "maliciousNodes": malicious_nodes,
                "simulation_time": run.simulation_time,
                "packet_rate": run.packet_rate,
                "attack_type": run.attack_type,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving simulation summary: {str(e)}")

@app.get("/api/network/nodes")
def get_network_nodes(run_id: Optional[str] = None):
    try:
        target_run_id = run_id or current_simulation.get("run_id")

        # 1. Attempt database-backed retrieval if target_run_id is available
        if target_run_id:
            try:
                from database import (
                    get_read_session,
                    SimulationRun,
                    NetworkNodeCoordinate,
                    NetworkEdge,
                )
                with get_read_session() as session:
                    run = session.query(SimulationRun).filter_by(run_id=target_run_id).first()
                    if run:
                        coords = (
                            session.query(NetworkNodeCoordinate)
                            .filter_by(simulation_run_id=run.id)
                            .order_by(NetworkNodeCoordinate.node_id.asc())
                            .all()
                        )
                        edges = (
                            session.query(NetworkEdge)
                            .filter_by(simulation_run_id=run.id)
                            .order_by(NetworkEdge.source_node.asc(), NetworkEdge.target_node.asc())
                            .all()
                        )

                        if coords:
                            n = run.num_nodes
                            maliciousNodes = (
                                json.loads(run.ground_truth_malicious)
                                if run.ground_truth_malicious
                                else []
                            )
                            attackEnabled = run.num_malicious > 0
                            source = current_simulation.get("sourceNode", 0) if target_run_id == current_simulation.get("run_id") else 0
                            dest = current_simulation.get("destNode", n - 1) if target_run_id == current_simulation.get("run_id") else n - 1

                            nodes = []
                            for i in range(n):
                                role = "Source" if i == source else "Destination" if i == dest else "Relay"
                                status = "malicious" if (attackEnabled and i in maliciousNodes) else "normal"
                                nodes.append({
                                    "id": i,
                                    "ip": f"10.1.1.{i+1}",
                                    "role": role,
                                    "status": status,
                                })

                            nodes_pos = {str(c.node_id): [c.x_coord, c.y_coord] for c in coords}
                            network_edges = [{"source": e.source_node, "target": e.target_node} for e in edges]
                            return {"nodes": nodes, "network_edges": network_edges, "nodes_pos": nodes_pos}
                    elif run_id:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Simulation run '{run_id}' not found in database."
                        )
            except HTTPException:
                raise
            except Exception:
                pass

        # 2. Disk fallback for uncommitted or active simulation runs
        n = current_simulation.get("nNodes", 8)
        attackEnabled = current_simulation.get("attackEnabled", False)
        maliciousNodes = current_simulation.get("maliciousNodes", [])
        
        source = current_simulation.get("sourceNode", 0)
        dest = current_simulation.get("destNode", n - 1)
        
        nodes = []
        for i in range(n):
            role = "Source" if i == source else "Destination" if i == dest else "Relay"
            status = "malicious" if (attackEnabled and i in maliciousNodes) else "normal"
            nodes.append({
                "id": i,
                "ip": f"10.1.1.{i+1}",
                "role": role,
                "status": status
            })
            
        network_edges = []
        nodes_pos = {}
        if target_run_id:
            topology_path = os.path.join(DYNAMIC_RESULTS_DIR, f"run_{target_run_id}_topology.json")
            if os.path.exists(topology_path):
                with open(topology_path, 'r') as f:
                    top_data = json.load(f)
                    network_edges = top_data.get("edges", [])
                    nodes_pos = top_data.get("nodes_pos", {})
            elif run_id:
                raise HTTPException(
                    status_code=404,
                    detail=f"Topology unavailable for simulation run '{run_id}'."
                )
                    
        return {"nodes": nodes, "network_edges": network_edges, "nodes_pos": nodes_pos}
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_network_nodes: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/simulation/metrics", response_model=List[FlowMetrics])
def get_dynamic_sim_metrics(run_id: Optional[str] = None):
    try:
        from app.services.results_service import get_simulation_metrics_from_db
        metrics = get_simulation_metrics_from_db(run_id=run_id)
        return [FlowMetrics(**m) for m in metrics]
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving simulation metrics: {str(e)}")

@app.get("/api/security/malicious-nodes")
def get_malicious_nodes():
    return {
        "attack_type": "Black Hole",
        "potential_attackers": [1, 2, 3, 4, 5, 6],
        "tested_attacker": 4,
        "description": "Drops unicast packets in RouteInput, spoofs high seqNo RREPs in RecvRequest"
    }

@app.get("/api/routing")
def get_routing_info():
    return {
        "protocol": "AODV",
        "hello_interval": "1s",
        "active_route_timeout": "3s",
        "attack_mechanism": "Fake RREP with Max SeqNo (65535) and HopCount=1"
    }

@app.get("/api/metrics", response_model=List[FlowMetrics])
def get_metrics():
    results = get_baseline_results()
    if not results:
        raise HTTPException(status_code=404, detail="Baseline results not found")
    return results

import csv

def parse_energy_csv(energy_csv_path: str) -> EnergyMetrics:
    if not energy_csv_path or not os.path.exists(energy_csv_path):
        return EnergyMetrics(available=False, average_percentage=0.0, nodes=[])
    
    nodes_data = []
    total_percentage = 0.0
    count = 0
    with open(energy_csv_path, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            initial = float(row.get("initial_energy_j", row.get("initial_energy", 0)))
            remaining = float(row.get("remaining_energy_j", row.get("remaining_energy", 0)))
            consumed = float(row.get("consumed_energy_j", row.get("consumed_energy", 0)))
            percentage = float(row.get("residual_energy_percent", row.get("residual_percentage", 0)))
            
            # Validation
            if initial <= 0:
                continue
            if remaining < 0 or consumed < 0:
                continue
            if percentage < 0 or percentage > 100:
                continue
            
            # Float validation (~0.01 tolerance)
            if abs(consumed - (initial - remaining)) > 0.01:
                continue
            expected_pct = (remaining / initial) * 100.0
            if abs(percentage - expected_pct) > 0.01:
                continue
            
            nodes_data.append({
                "node_id": int(row["node_id"]),
                "initial_energy_j": initial,
                "remaining_energy_j": remaining,
                "consumed_energy_j": consumed,
                "residual_energy_percent": percentage
            })
            total_percentage += percentage
            count += 1
            
    avg = total_percentage / count if count > 0 else 0.0
    return EnergyMetrics(available=True, average_percentage=avg, nodes=nodes_data)

@app.get("/api/metrics/comparison", response_model=ComparisonResponse)
def get_metrics_comparison(run_id: Optional[str] = None):
    try:
        from app.services.results_service import get_metrics_comparison_from_db
        res = get_metrics_comparison_from_db(run_id=run_id)
        return ComparisonResponse(
            baseline=FlowMetrics(**res["baseline"]),
            attack=FlowMetrics(**res["attack"]),
            maliciousNodes=res.get("maliciousNodes", []),
            pdr_drop_percent=res.get("pdr_drop_percent", 0.0),
            baseline_energy=EnergyMetrics(**res["baseline_energy"]) if res.get("baseline_energy") else None,
            current_run_energy=EnergyMetrics(**res["current_run_energy"]) if res.get("current_run_energy") else None,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving metrics comparison: {str(e)}")

@app.get("/api/trust/scores")
def api_get_trust_scores():
    scores = get_trust_scores()
    if not scores:
        raise HTTPException(status_code=404, detail="Trust dataset not found")
    return {"scores": scores}

@app.get("/api/trust/prediction")
def api_get_trust_prediction():
    predictions = get_trust_prediction()
    if not predictions:
        raise HTTPException(status_code=404, detail="Predictions not found")
    return {"predictions": predictions}

@app.get("/api/trust/dynamic")
def api_get_dynamic_trust(run_id: Optional[str] = None):
    """
    Returns authentic dynamic LSTM trust evaluations from the SQLite database.
    Supports filtering by specific run_id or defaults to latest active run.
    """
    try:
        from app.services.trust_service import get_dynamic_trust_from_db
        return get_dynamic_trust_from_db(run_id=run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving dynamic trust: {str(e)}")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _get_ml_metadata():
    meta_path = os.path.join(_BASE_DIR, "models", "baseline", "experiment_metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

@app.get("/api/ml/metrics")
def api_get_ml_metrics():
    """
    Retrieves classical ML evaluation metrics directly from the model_registry database table.
    """
    try:
        from database import get_read_session, ModelRegistry
        with get_read_session() as session:
            all_models = session.query(ModelRegistry).all()
            if not all_models:
                raise HTTPException(status_code=404, detail="ML metrics not found in database")
            metrics_dict = {}
            for m in all_models:
                cm = json.loads(m.confusion_matrix) if m.confusion_matrix else {}
                metrics_dict[m.model_name] = {
                    "Accuracy": m.accuracy,
                    "Precision": m.precision,
                    "Recall": m.recall,
                    "F1": m.f1_score,
                    "FPR": m.fpr,
                    "ConfusionMatrix": cm,
                }
            return {"metrics": metrics_dict}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving ML metrics from database: {str(e)}")

@app.get("/api/ml/features")
def api_get_ml_features():
    """
    Retrieves RFECV selected features from ModelRegistry active record.
    """
    try:
        from database import get_read_session, ModelRegistry
        with get_read_session() as session:
            rf = session.query(ModelRegistry).filter_by(model_name="RandomForest", is_active=True).first()
            if rf and rf.selected_features:
                return {"selected_features": json.loads(rf.selected_features)}
    except Exception:
        pass
    meta = _get_ml_metadata()
    return {"selected_features": meta.get("selected_features", [])}

@app.get("/api/ml/models")
def api_get_ml_models():
    """
    Retrieves active model names directly from the model_registry database table.
    """
    try:
        from database import get_read_session, ModelRegistry
        with get_read_session() as session:
            active_models = session.query(ModelRegistry).filter_by(is_active=True).all()
            if not active_models:
                raise HTTPException(status_code=404, detail="Active models not found in database")
            return {"models": [m.model_name for m in active_models]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving ML models from database: {str(e)}")
    meta = _get_ml_metadata()
    return {"models": meta.get("model_names", [])}

class PredictRequest(BaseModel):
    features: Dict[str, Any]
    model_name: Optional[str] = None
    model: Optional[str] = None

ALLOWED_ML_MODELS = {
    "randomforest": "RandomForest",
    "xgboost": "XGBoost",
    "catboost": "CatBoost",
    "svm": "SVM",
    "mlp": "MLP"
}

REQUIRED_SCALER_FEATURES = [
    "rx", "fw", "drop", "drop_ratio",
    "control_message_frequency", "network_avg_pdr", "network_avg_delay"
]

@app.post("/api/ml/predict")
def api_predict_ml(req: PredictRequest):
    """
    Stateless ad-hoc ML prediction endpoint for intrusion detection.
    Evaluates a single feature vector using authentic baseline ML models.
    Does NOT modify database, model registry, or weights.
    """
    import math
    import pandas as pd
    from app.ml.predict import MLPredictor

    # 1. Validate model_name (supporting both model_name and model for backward/test compatibility)
    raw_model = req.model_name or req.model or "RandomForest"
    model_key = raw_model.strip().lower()
    if model_key not in ALLOWED_ML_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model '{raw_model}'. Supported models: ['RandomForest', 'XGBoost', 'CatBoost', 'SVM', 'MLP']"
        )
    resolved_model_name = ALLOWED_ML_MODELS[model_key]

    # 2. Validate features dictionary
    if not isinstance(req.features, dict) or not req.features:
        raise HTTPException(
            status_code=400,
            detail="Request 'features' must be a non-empty dictionary of numeric values."
        )

    # 3. Check for missing required features
    missing_features = [f for f in REQUIRED_SCALER_FEATURES if f not in req.features]
    if missing_features:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required feature(s): {missing_features}. Required features: {REQUIRED_SCALER_FEATURES}"
        )

    # 4. Validate numeric types and reject NaN / Infinity
    clean_features = {}
    for f in REQUIRED_SCALER_FEATURES:
        val = req.features[f]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise HTTPException(
                status_code=400,
                detail=f"Feature '{f}' must be numeric, got {type(val).__name__}."
            )
        val_float = float(val)
        if math.isnan(val_float) or math.isinf(val_float):
            raise HTTPException(
                status_code=400,
                detail=f"Feature '{f}' must be a finite number; received NaN or Infinity."
            )
        clean_features[f] = val_float

    # 5. Execute inference through existing MLPredictor pipeline
    try:
        df_input = pd.DataFrame([clean_features])
        predictor = MLPredictor(model_name=resolved_model_name, experiment_name="baseline")
        res = predictor.predict(df_input)
    except ModuleNotFoundError as mne:
        raise HTTPException(
            status_code=503,
            detail=f"Model '{resolved_model_name}' runtime dependency is not installed: {str(mne)}"
        )
    except RuntimeError as re:
        raise HTTPException(
            status_code=500,
            detail=f"Model '{resolved_model_name}' loading error: {str(re)}"
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=f"Inference validation error: {str(ve)}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Inference error: {str(exc)}"
        )

    # 6. Map authentic prediction and class label (0 = Normal, 1 = Malicious)
    raw_pred = int(res["predictions"][0])
    label = "Malicious" if raw_pred == 1 else "Normal"

    prob_malicious = None
    if res.get("probabilities") is not None and len(res["probabilities"]) > 0:
        prob_malicious = float(res["probabilities"][0])

    return {
        "status": "success",
        "model": resolved_model_name,
        "prediction": raw_pred,
        "label": label,
        "probability_malicious": prob_malicious,
        "selected_features": res.get("selected_features_used", [])
    }

import os
import json

def get_fl_metrics_data(run_id: Optional[str] = None):
    fl_metrics_path = None
    if run_id:
        candidate = os.path.join(DYNAMIC_RESULTS_DIR, run_id, "fl", "fl_metrics.json")
        if os.path.exists(candidate):
            fl_metrics_path = candidate
        else:
            return None
    else:
        fl_metrics_path = current_simulation.get("fl_metrics_path")

    if not fl_metrics_path or not os.path.exists(fl_metrics_path):
        return None
    try:
        with open(fl_metrics_path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def get_fl_metrics_from_db(run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve authentic Federated Learning aggregation rounds and client metrics from SQLite.
    Queries FederatedLearningRound and FederatedLearningClient models.
    Falls back gracefully to disk-based fl_metrics.json if DB records are absent or simulation is uncommitted.
    """
    target_run_id = run_id or current_simulation.get("run_id")
    
    if target_run_id:
        try:
            from database import get_read_session, SimulationRun, FederatedLearningRound, FederatedLearningClient
            with get_read_session() as session:
                run = session.query(SimulationRun).filter_by(run_id=target_run_id).first()
                if run:
                    rounds = (
                        session.query(FederatedLearningRound)
                        .filter_by(simulation_run_id=run.id)
                        .order_by(FederatedLearningRound.round_number.asc())
                        .all()
                    )
                    if not rounds:
                        rounds = (
                            session.query(FederatedLearningRound)
                            .filter_by(session_id=target_run_id)
                            .order_by(FederatedLearningRound.round_number.asc())
                            .all()
                        )
                    if rounds:
                        rounds_data = []
                        for r in rounds:
                            clients = (
                                session.query(FederatedLearningClient)
                                .filter_by(round_id=r.id)
                                .order_by(FederatedLearningClient.client_id.asc())
                                .all()
                            )
                            rounds_data.append({
                                "round": r.round_number,
                                "global_loss": r.global_loss,
                                "global_accuracy": r.global_accuracy,
                                "clients": [
                                    {
                                        "client_id": c.client_id,
                                        "samples": c.samples_trained,
                                        "local_loss": c.local_loss,
                                        "local_accuracy": c.local_accuracy,
                                    }
                                    for c in clients
                                ],
                            })
                        return {
                            "status": "completed",
                            "reason": "",
                            "num_clients": rounds[0].participating_clients if rounds else 0,
                            "num_rounds": len(rounds),
                            "rounds": rounds_data,
                        }
        except Exception:
            pass

    return get_fl_metrics_data(run_id=target_run_id)


@app.get("/api/fl/status")
def get_fl_status(run_id: Optional[str] = None):
    data = get_fl_metrics_from_db(run_id=run_id)
    if not data:
        if not run_id and current_simulation.get("status") != "completed":
            raise HTTPException(status_code=404, detail="FL results unavailable. Simulation has not been run yet.")
        raise HTTPException(status_code=404, detail="FL results unavailable for current simulation run.")
    return {
        "status": data.get("status", "unknown"),
        "reason": data.get("reason", ""),
        "clients": data.get("num_clients", 0),
        "rounds": data.get("num_rounds", 0)
    }


@app.get("/api/fl/rounds")
def get_fl_rounds(run_id: Optional[str] = None):
    data = get_fl_metrics_from_db(run_id=run_id)
    if not data:
        raise HTTPException(status_code=404, detail="FL results unavailable for current simulation run.")
    return {
        "rounds": data.get("rounds", [])
    }


@app.get("/api/fl/clients")
def get_fl_clients(run_id: Optional[str] = None):
    data = get_fl_metrics_from_db(run_id=run_id)
    if not data:
        raise HTTPException(status_code=404, detail="FL results unavailable for current simulation run.")
    
    rounds = data.get("rounds", [])
    if not rounds:
        return {"clients": []}
        
    latest_round = rounds[-1]
    return {
        "clients": latest_round.get("clients", [])
    }


@app.get("/api/routing/path")
def api_get_routing_path(run_id: Optional[str] = None):
    """
    Returns authentic hop-by-hop routing records from the SQLite database.
    Queries the RoutingRecord model for phase='mitigated_pass2'.
    Supports filtering by specific run_id or defaults to latest active run.
    """
    try:
        from app.services.routing_service import get_routing_path_from_db
        return get_routing_path_from_db(run_id=run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving routing path: {str(e)}")

@app.get("/api/prevention/summary")
def get_prevention_summary(run_id: Optional[str] = None):
    """
    Returns a summary of the route recovery and prevention mechanism.
    If run_id is supplied, retrieves that exact run from the database.
    If run_id is omitted:
      - If active simulation is completed in memory, returns active state.
      - If backend is idle, resolves latest completed and persisted run from SQLite.
    """
    target_run_id = run_id or current_simulation.get("run_id")

    # 1. If run_id omitted and memory run_id unavailable, resolve latest eligible run from SQLite
    if not target_run_id:
        from database import get_read_session, SimulationRun
        try:
            with get_read_session() as session:
                latest_run = (
                    session.query(SimulationRun)
                    .filter_by(simulation_status="completed", persistence_status="completed")
                    .order_by(SimulationRun.id.desc())
                    .first()
                )
                if latest_run:
                    target_run_id = latest_run.run_id
                else:
                    return {
                        "status": "unavailable",
                        "reason": "No completed and persisted simulation run available yet."
                    }
        except Exception as e:
            return {
                "status": "unavailable",
                "reason": f"Database query failed: {str(e)}"
            }

    # 2. Check if run exists in DB
    from database import get_read_session, SimulationRun
    run_record = None
    if target_run_id:
        try:
            with get_read_session() as session:
                run_record = session.query(SimulationRun).filter_by(run_id=target_run_id).first()
                if not run_record and run_id:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Simulation run '{target_run_id}' not found."
                    )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error querying simulation run: {str(e)}")

    # 3. Determine simulation parameters
    if run_record:
        n = run_record.num_nodes
        malicious_nodes = json.loads(run_record.ground_truth_malicious) if run_record.ground_truth_malicious else []
        attack_enabled = run_record.num_malicious > 0
        effective_run_id = run_record.run_id
        source_node = 0
        dest_node = n - 1
        if effective_run_id == current_simulation.get("run_id"):
            source_node = current_simulation.get("sourceNode", 0)
            dest_node = current_simulation.get("destNode", n - 1)
    else:
        # In-memory active fallback when run_record is not in DB yet
        n = current_simulation.get("nNodes", 8)
        malicious_nodes = current_simulation.get("maliciousNodes", [])
        attack_enabled = current_simulation.get("attackEnabled", False)
        effective_run_id = current_simulation.get("run_id")
        source_node = current_simulation.get("sourceNode", 0)
        dest_node = current_simulation.get("destNode", n - 1)

    # 4. Get Trust Information (Predicted vs Ground Truth from SQLite DB)
    from app.services.trust_service import get_dynamic_trust_from_db
    try:
        trust_analysis = get_dynamic_trust_from_db(run_id=effective_run_id)
    except Exception:
        trust_analysis = get_dynamic_trust_analysis(
            nNodes=n,
            attackEnabled=attack_enabled,
            maliciousNodes=malicious_nodes,
            trace_csv_path=current_simulation.get("trace_csv_path") if effective_run_id == current_simulation.get("run_id") else None,
        )

    detected_low_trust = []
    trust_scores = {}
    for t in trust_analysis.get("lstm_predictions", []):
        node = t.get("node")
        trust_scores[node] = t.get("predicted_trust_score", t.get("trust_score", 0.0))
        if t.get("predicted_malicious") == 1 or t.get("is_malicious") == 1:
            if node not in detected_low_trust:
                detected_low_trust.append(node)

    # 5. Get Routing Paths (from SQLite DB)
    from app.services.routing_service import get_routing_path, get_routing_path_from_db

    # Baseline (Pass 1 - attack pass before trust is applied, if available in memory)
    original_route_data = {}
    if effective_run_id == current_simulation.get("run_id") and current_simulation.get("baseline_routing_json_path"):
        original_route_data = get_routing_path(
            routing_json_path=current_simulation.get("baseline_routing_json_path"),
            nNodes=n,
            attackEnabled=False,
            maliciousNodes=[],
            run_id=effective_run_id,
            sourceNode=source_node,
            destNode=dest_node,
        )

    # Recovered (Pass 2 - dynamic run from SQLite DB)
    try:
        recovered_route_data = get_routing_path_from_db(run_id=effective_run_id)
    except Exception:
        recovered_route_data = get_routing_path(
            routing_json_path=current_simulation.get("routing_json_path") if effective_run_id == current_simulation.get("run_id") else None,
            nNodes=n,
            attackEnabled=attack_enabled,
            maliciousNodes=malicious_nodes,
            run_id=effective_run_id,
            sourceNode=source_node,
            destNode=dest_node,
        )

    original_route = original_route_data.get("route", []) or original_route_data.get("route_nodes", [])
    recovered_route = recovered_route_data.get("route_nodes", []) or recovered_route_data.get("route", [])

    recovery_success = recovered_route_data.get("route_available", False)

    # 6. Determine authentic successfully isolated nodes from prevention events
    blocked_or_restricted_nodes = []
    prevention_data_status = "available"
    if run_record:
        from database import get_read_session, PreventionEvent
        try:
            with get_read_session() as session:
                successful_events = (
                    session.query(PreventionEvent.node_id)
                    .filter(
                        PreventionEvent.simulation_run_id == run_record.id,
                        PreventionEvent.execution_status == "SUCCESS"
                    )
                    .distinct()
                    .all()
                )
                blocked_or_restricted_nodes = sorted([ev[0] for ev in successful_events])
        except Exception as e:
            logger.warning(f"Failed to query prevention events for run '{effective_run_id}': {e}")
            blocked_or_restricted_nodes = []
            prevention_data_status = "query_error"
    else:
        prevention_data_status = "unpersisted"

    return {
        "run_id": effective_run_id,
        "num_nodes": n,
        "ground_truth_nodes": malicious_nodes,
        "source": source_node,
        "destination": dest_node,
        "detected_low_trust_nodes": detected_low_trust,
        "blocked_or_restricted_nodes": blocked_or_restricted_nodes,
        "original_route": original_route,
        "recovered_route": recovered_route,
        "original_hop_count": len(original_route) - 1 if len(original_route) > 0 else 0,
        "recovered_hop_count": len(recovered_route) - 1 if len(recovered_route) > 0 else 0,
        "recovery_success": recovery_success,
        "trust_scores": trust_scores,
        "trust_threshold": 0.5,
        "routing_method": "AODV-based routing enhanced with a Geographic Request Zone mechanism",
        "prevention_data_status": prevention_data_status,
    }


@app.get("/api/prevention/events")
def get_prevention_events(
    run_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Returns authentic chronological NS-3 prevention and mitigation event records
    directly from the SQLite database. Supports pagination via limit and offset.
    """
    target_run_id = run_id or current_simulation.get("run_id")
    if not target_run_id:
        raise HTTPException(status_code=400, detail="Missing run_id and no active simulation run.")

    from database import get_write_session, SimulationRun, PreventionEvent, ArtifactIngestionLedger
    with get_write_session() as session:
        run = session.query(SimulationRun).filter_by(run_id=target_run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail=f"Simulation run '{target_run_id}' not found.")

        # Check ledger status
        latest_ledger = (
            session.query(ArtifactIngestionLedger)
            .filter_by(simulation_run_id=run.id, artifact_type="prevention_events_json")
            .order_by(ArtifactIngestionLedger.attempt_number.desc())
            .first()
        )

        total_count = session.query(PreventionEvent).filter_by(simulation_run_id=run.id).count()

        events = (
            session.query(PreventionEvent)
            .filter_by(simulation_run_id=run.id)
            .order_by(PreventionEvent.sequence.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        event_items = [
            {
                "id": ev.id,
                "sequence": ev.sequence,
                "time_sec": ev.time_sec,
                "node_id": ev.node_id,
                "action_type": ev.action_type,
                "execution_status": ev.execution_status,
                "trigger_source": ev.trigger_source,
                "details": ev.details,
                "error_message": ev.error_message,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in events
        ]

        ledger_status = (
            latest_ledger.ingestion_status
            if latest_ledger
            else ("HISTORICAL_PILOT" if target_run_id == "20261111_225145_8e3c4f7c_8nodes_attack2_4" else "UNINGESTED")
        )

        return {
            "run_id": target_run_id,
            "simulation_run_id": run.id,
            "ledger_status": ledger_status,
            "total_events": total_count,
            "limit": limit,
            "offset": offset,
            "events": event_items,
        }

