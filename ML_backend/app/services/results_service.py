import csv
import json
import os
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, 'simulation', 'results')

def parse_csv(filepath: str) -> list:
    if not os.path.exists(filepath):
        return []
    
    results = []
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert values to correct types
            parsed_row = {
                "flow_id": int(row["flow_id"]),
                "source_addr": row["source_addr"],
                "dest_addr": row["dest_addr"],
                "tx_packets": int(row["tx_packets"]),
                "rx_packets": int(row["rx_packets"]),
                "lost_packets": int(row["lost_packets"]),
                "pdr_percent": float(row["pdr_percent"]),
                "throughput_kbps": float(row["throughput_kbps"]),
                "mean_delay_ms": float(row["mean_delay_ms"])
            }
            results.append(parsed_row)
    return results

def get_baseline_results() -> list:
    filepath = os.path.join(RESULTS_DIR, 'results.csv')
    return parse_csv(filepath)

def get_attack_results(node_id: int) -> list:
    filepath = os.path.join(RESULTS_DIR, f'attack_results_node{node_id}.csv')
    return parse_csv(filepath)

def get_main_flow(results: list) -> dict:
    # Flow 1 is the main UDP client→server flow
    for row in results:
        if row["flow_id"] == 1:
            return row
    if results:
        return results[0]
    return {}

def get_dynamic_results(csv_path: str) -> list:
    """Read metrics from a dynamic simulation run CSV (any path)."""
    if not csv_path:
        return []
    return parse_csv(csv_path)

def _format_energy_metrics(rows: list) -> dict:
    if not rows:
        return {"available": False, "average_percentage": 0.0, "nodes": []}
    nodes = [
        {
            "node_id": r.node_id,
            "initial_energy_j": r.initial_energy_j,
            "remaining_energy_j": r.remaining_energy_j,
            "consumed_energy_j": r.consumed_energy_j,
            "residual_energy_percent": r.residual_pct,
        }
        for r in rows
    ]
    avg_pct = sum(r.residual_pct for r in rows) / len(rows) if rows else 0.0
    return {"available": True, "average_percentage": avg_pct, "nodes": nodes}

def get_simulation_metrics_from_db(run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve flow metrics from the SQLite database for the specified run_id.
    Defaults to current active simulation run ID.
    Enforces strict temporary disk fallback only when ingestion is uncommitted.
    """
    from app.services.simulation_runner import current_simulation
    from database import get_read_session, SimulationRun, SimulationMetric

    target_run_id = run_id or current_simulation.get("run_id")
    if not target_run_id:
        return []

    with get_read_session() as session:
        run = session.query(SimulationRun).filter_by(run_id=target_run_id).first()
        if run:
            metrics = (
                session.query(SimulationMetric)
                .filter_by(simulation_run_id=run.id, phase="attack")
                .order_by(SimulationMetric.flow_id.asc())
                .all()
            )
            return [
                {
                    "flow_id": m.flow_id,
                    "source_addr": m.source_ip,
                    "dest_addr": m.dest_ip,
                    "tx_packets": m.tx_packets,
                    "rx_packets": m.rx_packets,
                    "lost_packets": m.tx_packets - m.rx_packets,
                    "pdr_percent": m.pdr,
                    "throughput_kbps": m.throughput_kbps,
                    "mean_delay_ms": m.avg_delay_ms,
                }
                for m in metrics
            ]

    # Temporary disk fallback: ONLY permitted if target run matches in-memory active run and ingestion is incomplete
    if (
        target_run_id == current_simulation.get("run_id")
        and current_simulation.get("csv_path")
        and os.path.exists(current_simulation["csv_path"])
        and current_simulation.get("persistence", {}).get("core", {}).get("status") not in ("SUCCESS", "ALREADY_INGESTED")
    ):
        return get_dynamic_results(current_simulation["csv_path"])

    raise KeyError(f"Simulation run '{target_run_id}' not found in database.")

def get_metrics_comparison_from_db(run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve baseline vs attack flow comparison and energy metrics from SQLite.
    Maintains exact ComparisonResponse contract.
    """
    from app.services.simulation_runner import current_simulation
    from database import get_read_session, SimulationRun, SimulationMetric, NodeEnergyMetric

    target_run_id = run_id or current_simulation.get("run_id")

    with get_read_session() as session:
        # If no dynamic simulation run exists yet, load baseline comparison from first completed baseline run
        if not target_run_id or (current_simulation.get("status") != "completed" and not run_id):
            base_run = session.query(SimulationRun).filter_by(simulation_status="completed").first()
            if base_run:
                b_metrics = (
                    session.query(SimulationMetric)
                    .filter_by(simulation_run_id=base_run.id, phase="baseline")
                    .order_by(SimulationMetric.flow_id.asc())
                    .all()
                )
                b_energy = (
                    session.query(NodeEnergyMetric)
                    .filter_by(simulation_run_id=base_run.id, phase="baseline")
                    .order_by(NodeEnergyMetric.node_id.asc())
                    .all()
                )
                b_flow_list = [
                    {
                        "flow_id": m.flow_id,
                        "source_addr": m.source_ip,
                        "dest_addr": m.dest_ip,
                        "tx_packets": m.tx_packets,
                        "rx_packets": m.rx_packets,
                        "lost_packets": m.tx_packets - m.rx_packets,
                        "pdr_percent": m.pdr,
                        "throughput_kbps": m.throughput_kbps,
                        "mean_delay_ms": m.avg_delay_ms,
                    }
                    for m in b_metrics
                ]
                b_main = get_main_flow(b_flow_list)
                if b_main:
                    energy_dict = _format_energy_metrics(b_energy)
                    return {
                        "baseline": b_main,
                        "attack": b_main,
                        "maliciousNodes": [],
                        "pdr_drop_percent": 0.0,
                        "baseline_energy": energy_dict,
                        "current_run_energy": energy_dict,
                    }

        # Otherwise query the requested or active run
        if target_run_id:
            run = session.query(SimulationRun).filter_by(run_id=target_run_id).first()
            if run:
                b_metrics = (
                    session.query(SimulationMetric)
                    .filter_by(simulation_run_id=run.id, phase="baseline")
                    .order_by(SimulationMetric.flow_id.asc())
                    .all()
                )
                a_metrics = (
                    session.query(SimulationMetric)
                    .filter_by(simulation_run_id=run.id, phase="attack")
                    .order_by(SimulationMetric.flow_id.asc())
                    .all()
                )
                b_energy = (
                    session.query(NodeEnergyMetric)
                    .filter_by(simulation_run_id=run.id, phase="baseline")
                    .order_by(NodeEnergyMetric.node_id.asc())
                    .all()
                )
                a_energy = (
                    session.query(NodeEnergyMetric)
                    .filter_by(simulation_run_id=run.id, phase="attack")
                    .order_by(NodeEnergyMetric.node_id.asc())
                    .all()
                )

                b_flows = [
                    {
                        "flow_id": m.flow_id,
                        "source_addr": m.source_ip,
                        "dest_addr": m.dest_ip,
                        "tx_packets": m.tx_packets,
                        "rx_packets": m.rx_packets,
                        "lost_packets": m.tx_packets - m.rx_packets,
                        "pdr_percent": m.pdr,
                        "throughput_kbps": m.throughput_kbps,
                        "mean_delay_ms": m.avg_delay_ms,
                    }
                    for m in b_metrics
                ]
                a_flows = [
                    {
                        "flow_id": m.flow_id,
                        "source_addr": m.source_ip,
                        "dest_addr": m.dest_ip,
                        "tx_packets": m.tx_packets,
                        "rx_packets": m.rx_packets,
                        "lost_packets": m.tx_packets - m.rx_packets,
                        "pdr_percent": m.pdr,
                        "throughput_kbps": m.throughput_kbps,
                        "mean_delay_ms": m.avg_delay_ms,
                    }
                    for m in a_metrics
                ]

                b_main = get_main_flow(b_flows)
                a_main = get_main_flow(a_flows)

                if not b_main or not a_main:
                    raise ValueError(f"Main flow not found in database metrics for run '{target_run_id}'.")

                pdr_drop = round(b_main["pdr_percent"] - a_main["pdr_percent"], 2)
                malicious_nodes = json.loads(run.ground_truth_malicious) if run.ground_truth_malicious else []

                return {
                    "baseline": b_main,
                    "attack": a_main,
                    "maliciousNodes": malicious_nodes,
                    "pdr_drop_percent": pdr_drop,
                    "baseline_energy": _format_energy_metrics(b_energy),
                    "current_run_energy": _format_energy_metrics(a_energy),
                }

    # Temporary disk fallback if ingestion incomplete
    if (
        target_run_id == current_simulation.get("run_id")
        and current_simulation.get("csv_path")
        and current_simulation.get("persistence", {}).get("core", {}).get("status") not in ("SUCCESS", "ALREADY_INGESTED")
    ):
        from app.main import parse_energy_csv  # disk parser fallback
        baseline_csv = current_simulation.get("baseline_csv_path")
        if baseline_csv and os.path.exists(baseline_csv):
            b_results = get_dynamic_results(baseline_csv)
        else:
            b_results = get_baseline_results()
        a_results = get_dynamic_results(current_simulation["csv_path"])
        b_main = get_main_flow(b_results)
        a_main = get_main_flow(a_results)
        if b_main and a_main:
            pdr_drop = round(b_main["pdr_percent"] - a_main["pdr_percent"], 2)
            return {
                "baseline": b_main,
                "attack": a_main,
                "maliciousNodes": current_simulation.get("maliciousNodes", []),
                "pdr_drop_percent": pdr_drop,
                "baseline_energy": parse_energy_csv(current_simulation.get("baseline_energy_csv_path")).model_dump(),
                "current_run_energy": parse_energy_csv(current_simulation.get("energy_csv_path")).model_dump(),
            }

    raise KeyError(f"Simulation run '{target_run_id}' not found in database.")


