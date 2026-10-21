from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

import os
import json
from app.services.results_service import get_baseline_results, get_attack_results, get_main_flow
from app.services.simulation_runner import current_simulation, DYNAMIC_RESULTS_DIR
from app.services.trust_service import get_trust_scores, get_trust_prediction, get_ml_metrics, get_dynamic_trust_analysis
from app.services.routing_service import get_routing_path

app = FastAPI(title="MANET Trust-Aware Routing Backend")

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
    
    try:
        dest_node = req.destinationNode if req.destinationNode is not None else req.nNodes - 1
        if req.sourceNode < 0 or req.sourceNode >= req.nNodes:
             raise HTTPException(status_code=400, detail="Invalid source node")
        if dest_node < 0 or dest_node >= req.nNodes:
             raise HTTPException(status_code=400, detail="Invalid destination node")
        if req.sourceNode == dest_node:
             raise HTTPException(status_code=400, detail="Source and destination cannot be the same")
        
        res = run_simulation(req.nNodes, maliciousNodes=malicious_nodes, attackEnabled=req.attackEnabled, seed=req.seed, simArea=req.simArea, demoTopology=req.demoTopology, sourceNode=req.sourceNode, destNode=dest_node)
        return res
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
        "classical_ml": current_simulation.get("classical_ml", None)
    }

@app.get("/api/simulation/summary")
def get_simulation_summary():
    n = current_simulation["nNodes"]
    return {
        "num_nodes": n,
        "area": "300x300m",
        "mobility": "RandomWaypoint",
        "routing": "AODV-based routing enhanced with a Geographic Request Zone mechanism",
        "duration_seconds": 60,
        "sourceNode": current_simulation.get("sourceNode", 0),
        "destinationNode": current_simulation.get("destNode", n - 1),
        "main_flow": f"Node {current_simulation.get('sourceNode', 0)} (10.1.1.{current_simulation.get('sourceNode', 0) + 1}) to Node {current_simulation.get('destNode', n-1)} (10.1.1.{current_simulation.get('destNode', n-1) + 1})",
        "attackEnabled": current_simulation.get("attackEnabled", False),
        "maliciousNodes": current_simulation.get("maliciousNodes", [])
    }

@app.get("/api/network/nodes")
def get_network_nodes():
    try:
        n = current_simulation["nNodes"]
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
        if current_simulation["run_id"]:
            topology_path = os.path.join(DYNAMIC_RESULTS_DIR, f"run_{current_simulation['run_id']}_topology.json")
            if os.path.exists(topology_path):
                with open(topology_path, 'r') as f:
                    top_data = json.load(f)
                    network_edges = top_data.get("edges", [])
                    nodes_pos = top_data.get("nodes_pos", {})
                    
        return {"nodes": nodes, "network_edges": network_edges, "nodes_pos": nodes_pos}
    except Exception as e:
        print(f"ERROR in get_network_nodes: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/simulation/metrics", response_model=List[FlowMetrics])
def get_dynamic_sim_metrics():
    if current_simulation["status"] != "completed" or not current_simulation["csv_path"]:
        return []
    
    results = get_dynamic_results(current_simulation["csv_path"])
    if not results:
        return []
    return results

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
def get_metrics_comparison():
    # Load attack/current results from current_simulation
    if current_simulation["status"] != "completed" or not current_simulation.get("csv_path"):
        # Fallback to returning baseline vs baseline if no dynamic simulation is run yet
        baseline_results = get_baseline_results()
        baseline_energy = EnergyMetrics(available=False, average_percentage=0.0, nodes=[])
        attack_results = baseline_results
        malicious_nodes = []
        current_run_energy = baseline_energy
    else:
        from app.services.results_service import get_dynamic_results
        baseline_csv = current_simulation.get("baseline_csv_path")
        if baseline_csv and os.path.exists(baseline_csv):
            baseline_results = get_dynamic_results(baseline_csv)
        else:
            baseline_results = get_baseline_results()
        
        baseline_energy = parse_energy_csv(current_simulation.get("baseline_energy_csv_path"))

        attack_results = get_dynamic_results(current_simulation["csv_path"])
        malicious_nodes = current_simulation.get("maliciousNodes", [])
        current_run_energy = parse_energy_csv(current_simulation.get("energy_csv_path"))
        
    if not baseline_results or not attack_results:
        raise HTTPException(status_code=404, detail="Simulation results not found")
        
    baseline_main = get_main_flow(baseline_results)
    attack_main = get_main_flow(attack_results)
    
    if not baseline_main or not attack_main:
        raise HTTPException(status_code=404, detail="Main flow (Flow 1) not found in results")
        
    pdr_drop = baseline_main["pdr_percent"] - attack_main["pdr_percent"]
    
    return ComparisonResponse(
        baseline=FlowMetrics(**baseline_main),
        attack=FlowMetrics(**attack_main),
        maliciousNodes=malicious_nodes,
        pdr_drop_percent=round(pdr_drop, 2),
        baseline_energy=baseline_energy,
        current_run_energy=current_run_energy
    )

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
def api_get_dynamic_trust():
    """
    Returns trust analysis scoped to the CURRENT dynamic simulation run.

    - Uses the actual NS-3 trace CSV (if NS-3 produced one) to derive behaviour.
    - Runs LSTM inference on those real features.
    - Does NOT hardcode any attacker node.
    - When no dynamic run exists, reports status=idle.
    """
    if current_simulation["status"] not in ("completed",):
        return {
            "status": current_simulation["status"],
            "run_config": {
                "nNodes":        current_simulation["nNodes"],
                "attackEnabled": current_simulation.get("attackEnabled", False),
                "maliciousNodes": current_simulation.get("maliciousNodes", []),
            },
            "nodes":            [],
            "lstm_predictions": [],
            "lstm_status":      "unavailable",
            "lstm_reason":      "No completed simulation run available yet.",
            "trace_available":  False,
        }

    result = get_dynamic_trust_analysis(
        nNodes=current_simulation["nNodes"],
        attackEnabled=current_simulation.get("attackEnabled", False),
        maliciousNodes=current_simulation.get("maliciousNodes", []),
        trace_csv_path=current_simulation.get("trace_csv_path"),
    )
    result["status"] = "completed"
    return result

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
    meta = _get_ml_metadata()
    if not meta.get("metrics"):
        raise HTTPException(status_code=404, detail="ML metrics not found")
    return {"metrics": meta["metrics"]}

@app.get("/api/ml/features")
def api_get_ml_features():
    meta = _get_ml_metadata()
    return {"selected_features": meta.get("selected_features", [])}

@app.get("/api/ml/models")
def api_get_ml_models():
    meta = _get_ml_metadata()
    return {"models": meta.get("model_names", [])}

import os
import json

def get_fl_metrics_data():
    fl_metrics_path = current_simulation.get("fl_metrics_path")
    if not fl_metrics_path or not os.path.exists(fl_metrics_path):
        return None
    try:
        with open(fl_metrics_path, "r") as f:
            return json.load(f)
    except Exception:
        return None

@app.get("/api/fl/status")
def get_fl_status():
    data = get_fl_metrics_data()
    if not data:
        if current_simulation["status"] != "completed":
            raise HTTPException(status_code=404, detail="FL results unavailable. Simulation has not been run yet.")
        raise HTTPException(status_code=404, detail="FL results unavailable for current simulation run.")
    return {
        "status": data.get("status", "unknown"),
        "reason": data.get("reason", ""),
        "clients": data.get("num_clients", 0),
        "rounds": data.get("num_rounds", 0)
    }

@app.get("/api/fl/rounds")
def get_fl_rounds():
    data = get_fl_metrics_data()
    if not data:
        raise HTTPException(status_code=404, detail="FL results unavailable for current simulation run.")
    return {
        "rounds": data.get("rounds", [])
    }

@app.get("/api/fl/clients")
def get_fl_clients():
    data = get_fl_metrics_data()
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
def api_get_routing_path():
    """
    Returns the actual hop-by-hop routing path for the current dynamic
    simulation run, extracted from the NS-3 ASCII IPv4 trace.

    - Source is always Node 0; destination is Node N-1.
    - Hops are real IPv4 receive events, NOT inferred from positions.
    - When route data is unavailable, returns route_available=False with a
      clear explanation. Never fabricates hops.
    """
    return get_routing_path(
        routing_json_path = current_simulation.get("routing_json_path"),
        nNodes            = current_simulation["nNodes"],
        attackEnabled     = current_simulation.get("attackEnabled", False),
        maliciousNodes    = current_simulation.get("maliciousNodes", []),
        run_id            = current_simulation.get("run_id"),
        sourceNode        = current_simulation.get("sourceNode", 0),
        destNode          = current_simulation.get("destNode", current_simulation["nNodes"] - 1),
    )

@app.get("/api/prevention/summary")
def get_prevention_summary():
    """
    Returns a read-only summary of the route recovery and prevention mechanism,
    derived purely from the latest NS-3 simulation outputs.
    """
    if current_simulation["status"] != "completed":
        return {
            "status": "unavailable",
            "reason": "No completed simulation run available yet."
        }
        
    n = current_simulation["nNodes"]
    source_node = current_simulation.get("sourceNode", 0)
    dest_node = current_simulation.get("destNode", n - 1)
    
    # 1. Get Trust Information (Predicted vs Ground Truth)
    trust_analysis = get_dynamic_trust_analysis(
        nNodes=n,
        attackEnabled=current_simulation.get("attackEnabled", False),
        maliciousNodes=current_simulation.get("maliciousNodes", []),
        trace_csv_path=current_simulation.get("trace_csv_path"),
    )
    
    detected_low_trust = []
    trust_scores = {}
    for t in trust_analysis.get("lstm_predictions", []):
        node = t.get("node")
        trust_scores[node] = t.get("predicted_trust_score", t.get("trust_score", 0.0))
        # If model classified as malicious
        if t.get("predicted_malicious") == 1 or t.get("is_malicious") == 1:
            detected_low_trust.append(node)
            
    # 2. Get Routing Paths
    from app.services.routing_service import get_routing_path
    
    # Baseline (Pass 1 - attack pass before trust is applied, if available. Otherwise, just original baseline)
    # The current architecture uses baseline_routing_json_path for clean network,
    # but the prevention original route should be the path attempted during the attack (which failed).
    # Since we don't save Pass 1 route trace separately, we'll use the clean baseline route as the "original intended route".
    original_route_data = get_routing_path(
        routing_json_path = current_simulation.get("baseline_routing_json_path"),
        nNodes = n,
        attackEnabled = False,
        maliciousNodes = [],
        run_id = current_simulation.get("run_id"),
        sourceNode = source_node,
        destNode = dest_node
    )
    
    # Recovered (Pass 2 - dynamic run)
    recovered_route_data = get_routing_path(
        routing_json_path = current_simulation.get("routing_json_path"),
        nNodes = n,
        attackEnabled = current_simulation.get("attackEnabled", False),
        maliciousNodes = current_simulation.get("maliciousNodes", []),
        run_id = current_simulation.get("run_id"),
        sourceNode = source_node,
        destNode = dest_node
    )
    
    original_route = original_route_data.get("route", [])
    recovered_route = recovered_route_data.get("route", [])
    
    recovery_success = recovered_route_data.get("route_available", False)
    
    # blocked_or_restricted_nodes includes detected malicious + those outside LAR Request Zone.
    # We don't parse the LAR stdout right now, so we state the ones explicitly blocked by LSTM.
    blocked_or_restricted_nodes = detected_low_trust.copy()
    
    return {
        "run_id": current_simulation.get("run_id"),
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
        "routing_method": "AODV-based routing enhanced with a Geographic Request Zone mechanism"
    }
