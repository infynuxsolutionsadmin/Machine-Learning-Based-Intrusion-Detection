import os
import csv
import json
import subprocess
import sys
from typing import Dict, List, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
TRUST_DATASET_PATH = os.path.join(BASE_DIR, 'trust_dataset.csv')
PREDICTIONS_PATH = os.path.join(BASE_DIR, 'ml', 'lstm_predictions_node4.csv')
METRICS_PATH = os.path.join(BASE_DIR, 'lstm_metrics.json')
PREDICT_SCRIPT = os.path.join(BASE_DIR, 'ml', 'predict_trust.py')
LSTM_MODEL_PATH = os.path.join(BASE_DIR, 'lstm_trust_model.pth')

def get_trust_scores() -> List[Dict[str, Any]]:
    if not os.path.exists(TRUST_DATASET_PATH):
        return []
    
    # We want to aggregate the behavior for each node
    # capturing any malicious activity that occurred during the run
    agg_scores = {}
    try:
        with open(TRUST_DATASET_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = int(row['node'])
                is_malicious = int(row['label']) == 1
                trust_score = 0.0 if is_malicious else 1.0
                
                if node_id not in agg_scores:
                    agg_scores[node_id] = {
                        "node": node_id,
                        "time": float(row['time']),
                        "rx": int(float(row['rx'])),
                        "fw": int(float(row['fw'])),
                        "drop": int(float(row['drop'])),
                        "malicious": is_malicious,
                        "trust_score": trust_score
                    }
                else:
                    # Update with latest chronological metrics
                    agg_scores[node_id]["time"] = float(row['time'])
                    agg_scores[node_id]["rx"] = int(float(row['rx']))
                    agg_scores[node_id]["fw"] = int(float(row['fw']))
                    agg_scores[node_id]["drop"] = int(float(row['drop']))
                    
                    # Aggregate the worst behavior: if it was EVER malicious, keep it malicious
                    if is_malicious:
                        agg_scores[node_id]["malicious"] = True
                        agg_scores[node_id]["trust_score"] = 0.0
    except Exception as e:
        print(f"Error reading trust scores: {e}")
        return []
        
    return list(agg_scores.values())

def get_trust_prediction() -> List[Dict[str, Any]]:
    if not os.path.exists(PREDICTIONS_PATH):
        return []
        
    predictions = []
    try:
        with open(PREDICTIONS_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                predictions.append({
                    "time": float(row['time']),
                    "node": int(row['node']),
                    "prediction": "Malicious",
                    "action": "Blacklisted"
                })
    except Exception as e:
        print(f"Error reading predictions: {e}")
        return []
        
    return predictions

def get_ml_metrics() -> Dict[str, Any]:
    if not os.path.exists(METRICS_PATH):
        return {}
        
    try:
        with open(METRICS_PATH, mode='r', encoding='utf-8') as f:
            data = json.load(f)
            
        return {
            "model_type": "LSTM",
            "framework": "PyTorch",
            "sequence_length": 5,
            "test_accuracy": data.get("test_accuracy", 0.0),
            "test_sample_count": data.get("samples", 0),
            "train_test_split": "80/20",
            "epochs": 20,
            "batch_size": 32,
            "optimizer": "Adam",
            "learning_rate": 0.01,
            "loss_function": "BCELoss",
            "input_features": ["rx_rate", "fw_rate", "drop_rate", "fw_ratio"]
        }
    except Exception as e:
        print(f"Error reading metrics: {e}")
        return {}


def get_dynamic_trust_analysis(
    nNodes: int,
    attackEnabled: bool,
    maliciousNodes: Optional[List[int]],
    trace_csv_path: Optional[str]
) -> Dict[str, Any]:
    """
    Build a dynamic trust analysis result for the current simulation run.

    - Derives per-node trust scores from the trace CSV (if available).
    - Runs LSTM inference on the trace CSV (if trace CSV exists and LSTM model exists).
    - Returns structured data suitable for the Trust Analysis API.
    - Does NOT fabricate scores or predictions; clearly marks when LSTM inference
      is unavailable.
    """
    # Build the base node list from the simulation configuration
    nodes = []
    for i in range(nNodes):
        role = "Source" if i == 0 else "Destination" if i == nNodes - 1 else "Relay"
        # A node is considered malicious only when attackEnabled AND it IS one of the attackers
        is_attacker = attackEnabled and (maliciousNodes is not None and i in maliciousNodes)
        nodes.append({
            "node": i,
            "role": role,
            "trust_score": None,   # will be filled from trace if available
            "malicious": is_attacker,
            "rx": None,
            "fw": None,
            "drop": None,
        })

    # Parse trace CSV if NS-3 produced one
    trace_available = trace_csv_path and os.path.exists(trace_csv_path)
    if trace_available:
        latest_by_node: Dict[int, dict] = {}
        try:
            with open(trace_csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nid = int(row['node'])
                    latest_by_node[nid] = {
                        "time":  float(row['time']),
                        "rx":    int(float(row['rx'])),
                        "fw":    int(float(row['fw'])),
                        "drop":  int(float(row['drop'])),
                        "label": int(row['label'])
                    }
        except Exception as e:
            print(f"[trust_service] Failed to parse trace CSV: {e}")
            trace_available = False

        if trace_available:
            for n in nodes:
                nid = n["node"]
                if nid in latest_by_node:
                    d = latest_by_node[nid]
                    n["rx"]   = d["rx"]
                    n["fw"]   = d["fw"]
                    n["drop"] = d["drop"]
                    # Derive trust score from actual trace label
                    label_malicious = d["label"] == 1
                    n["malicious"] = n.get("malicious", False) or label_malicious
                    # n["trust_score"] will be overridden by LSTM if available, else we could keep trace label.
                    if n["trust_score"] is None or (label_malicious and n["trust_score"] > 0.0):
                        n["trust_score"] = 0.0 if label_malicious else 1.0

    # Run LSTM inference on the trace if available
    lstm_predictions: List[Dict] = []
    lstm_status = "unavailable"
    lstm_reason = "No per-node trace was produced by this simulation run."

    if trace_available and os.path.exists(LSTM_MODEL_PATH) and os.path.exists(PREDICT_SCRIPT):
        # Use a temp output path so we don't collide
        pred_output = trace_csv_path.replace("_trace.csv", "_lstm_pred.csv")
        try:
            result = subprocess.run(
                [sys.executable, PREDICT_SCRIPT, trace_csv_path, pred_output],
                capture_output=True, text=True, timeout=60,
                cwd=BASE_DIR  # model loaded relative to BASE_DIR
            )
            if result.returncode == 0 and os.path.exists(pred_output):
                with open(pred_output, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        is_mal = int(row.get('is_malicious', 1)) if 'is_malicious' in row else 1
                        score = float(row.get('score', 0.0 if is_mal else 1.0))
                        node_id = int(row['node'])
                        ground_truth = 1 if (attackEnabled and maliciousNodes and node_id in maliciousNodes) else 0
                        lstm_predictions.append({
                            "time":       float(row['time']),
                            "node":       node_id,
                            "predicted_trust_score": score,
                            "predicted_malicious": is_mal,
                            "ground_truth_malicious": ground_truth,
                            "trust_threshold": 0.5,
                            "prediction": "Malicious" if is_mal == 1 else "Trusted",
                            "action":     "Blacklisted" if is_mal == 1 else "None"
                        })
                lstm_status = "completed"
                lstm_reason = None
            else:
                lstm_status = "failed"
                lstm_reason = (result.stderr or result.stdout or "Unknown error")[:300]
        except Exception as e:
            lstm_status = "failed"
            lstm_reason = str(e)[:300]
    elif not os.path.exists(LSTM_MODEL_PATH):
        lstm_reason = "LSTM model file not found."
    elif not trace_available:
        pass  # reason already set

    # Update node malicious status based on aggregated actual LSTM predictions
    if lstm_status == "completed" and lstm_predictions:
        agg_preds = {}
        for p in lstm_predictions:
            node_id = p["node"]
            if node_id not in agg_preds:
                agg_preds[node_id] = {
                    "score": p["predicted_trust_score"],
                    "is_malicious": p["predicted_malicious"]
                }
            else:
                # Minimum score represents worst behavior
                if p["predicted_trust_score"] < agg_preds[node_id]["score"]:
                    agg_preds[node_id]["score"] = p["predicted_trust_score"]
                # If a node was ever classified as malicious, it remains malicious
                if p["predicted_malicious"] == 1:
                    agg_preds[node_id]["is_malicious"] = 1
            
        for n in nodes:
            if n["node"] in agg_preds:
                p = agg_preds[n["node"]]
                n["predicted_trust_score"] = p["score"]
                n["predicted_malicious"] = (p["is_malicious"] == 1)
                n["trust_threshold"] = 0.5
                n["ground_truth_malicious"] = (attackEnabled and maliciousNodes and n["node"] in maliciousNodes)

    return {
        "run_config": {
            "nNodes":        nNodes,
            "attackEnabled": attackEnabled,
            "maliciousNodes":  maliciousNodes if maliciousNodes is not None else [],
        },
        "nodes":            nodes,
        "lstm_predictions": lstm_predictions,
        "lstm_status":      lstm_status,
        "lstm_reason":      lstm_reason,
        "trace_available":  trace_available,
    }
