import csv
import os

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
    return {}

def get_dynamic_results(csv_path: str) -> list:
    """Read metrics from a dynamic simulation run CSV (any path)."""
    if not csv_path:
        return []
    return parse_csv(csv_path)

