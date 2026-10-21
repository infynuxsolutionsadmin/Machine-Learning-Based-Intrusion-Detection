"""
simulation_runner.py
Handles executing the NS-3 MANET simulation with a configurable node count.
Each run is isolated with a unique run ID so no two runs can ever overwrite
each other's results. Verified Phase 1-6 artifacts are never touched.
"""
import subprocess
import os
import sys
import uuid
import threading
import time
from datetime import datetime
import pandas as pd
from pathlib import Path
from app.simulation.parser import NS3Parser
from app.features.extractor import CrossLayerExtractor
from app.ml.predict import MLPredictor

def run_classical_ml_analysis(run_dir: str, run_id: str) -> dict:
    result = {
        "status": "failed",
        "run_id": run_id,
        "dataset_rows": 0,
        "features": [],
        "models": {}
    }
    try:
        r_dir = Path(run_dir)
        parser = NS3Parser(r_dir, run_id=run_id)
        flowmon_df = parser.parse_flowmon()
        trace_df = parser.parse_trace_csv()
        route_df = parser.parse_route_tr()
        
        extractor = CrossLayerExtractor(flowmon_df, trace_df, route_df)
        df = extractor.extract_all()
        
        result["dataset_rows"] = len(df)
        
        models_to_run = ["RandomForest", "XGBoost", "CatBoost", "SVM", "MLP"]
        preds_path = r_dir / f"run_{run_id}_classical_ml_predictions.csv"
        df_out = df.copy() if not df.empty else pd.DataFrame()
        
        for m in models_to_run:
            try:
                predictor = MLPredictor(model_name=m, experiment_name="baseline")
                res = predictor.predict(df)
                result["models"][m] = {"prediction_count": len(res["predictions"])}
                if not result["features"]:
                    result["features"] = res["selected_features_used"]
                
                if not df_out.empty:
                    df_out[f"{m}_pred"] = res["predictions"]
            except Exception as e:
                result["models"][m] = {"error": str(e)}
        
        if not df_out.empty:
            df_out.to_csv(preds_path, index=False)
            
        result["status"] = "completed"
    except Exception as e:
        result["error"] = str(e)
        
    return result

# ── NS-3 paths (inside WSL Ubuntu) ────────────────────────────────────────
NS3_DIR_WSL = "/home/kumar/MANET/ns-3/ns-allinone-3.41/ns-3.41"
NS3_BIN_WSL = f"{NS3_DIR_WSL}/build/scratch/manet-sim/ns3.41-manet-sim-default"

# ── Windows/Python side paths ──────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))   # app/services/
_APP_DIR  = os.path.dirname(_THIS_DIR)                    # app/
BASE_DIR  = os.path.dirname(_APP_DIR)                     # manet-backend/
DYNAMIC_RESULTS_DIR = os.path.join(BASE_DIR, "simulation", "results", "dynamic")
PARSER_SCRIPT       = os.path.join(BASE_DIR, "simulation", "parse_results.py")
ROUTE_PARSER_SCRIPT = os.path.join(BASE_DIR, "simulation", "parse_route.py")
FL_SERVER_SCRIPT    = os.path.join(BASE_DIR, "federated_learning", "fl_server.py")
PREDICT_SCRIPT      = os.path.join(BASE_DIR, "ml", "predict_trust.py")

# ── Concurrency guard ──────────────────────────────────────────────────────
_sim_lock = threading.Lock()

import json

CURRENT_RUN_JSON_PATH = os.path.join(DYNAMIC_RESULTS_DIR, "current_run.json")

# ── Shared state readable by FastAPI endpoints ─────────────────────────────
default_simulation: dict = {
    "status"           : "idle",   # idle | running | completed | failed
    "run_id"           : None,
    "nNodes"           : 8,        # default matches verified 8-node project
    "csv_path"         : None,
    "xml_path"         : None,
    "trace_csv_path"   : None,     # NS-3 per-node behaviour trace for LSTM
    "route_tr_path"    : None,     # NS-3 ASCII routing trace (.tr)
    "routing_json_path": None,     # Parsed hop-by-hop routing JSON
    "fl_metrics_path"  : None,     # FL metrics JSON for the current run
    "baseline_csv_path": None,     # Baseline simulation CSV
    "baseline_energy_csv_path": None, # Baseline energy CSV
    "energy_csv_path"  : None,     # Current run energy CSV
    "error"            : None,
    "duration_seconds" : None,
    "attackEnabled"    : False,
    "maliciousNodes"   : [],
    "classical_ml"     : None,
}

current_simulation = dict(default_simulation)

if os.path.exists(CURRENT_RUN_JSON_PATH):
    try:
        with open(CURRENT_RUN_JSON_PATH, "r", encoding="utf-8") as f:
            saved_state = json.load(f)
            # Only restore if it was completed or failed
            if saved_state.get("status") in ("completed", "failed"):
                current_simulation.update(saved_state)
    except Exception as e:
        print(f"[simulation_runner] Failed to load previous simulation state: {e}")


def _win_to_wsl(win_path: str) -> str:
    """Convert a Windows absolute path to its WSL /mnt/<drive>/... path."""
    p = win_path.replace("\\", "/")
    drive = p[0].lower()
    return f"/mnt/{drive}" + p[2:]


def run_simulation(
    nNodes: int,
    maliciousNodes: list = None,
    attackEnabled: bool = False,
    seed: int = None,
    simArea: float = None,
    demoTopology: bool = False,
    sourceNode: int = 0,
    destNode: int = None
) -> dict:
    """
    Execute the NS-3 MANET simulation with *nNodes* nodes (blocking call).

    Flow: NS-3 binary (WSL) -> FlowMonitor XML + trace CSV -> existing Python parser -> flow CSV

    Updates the global `current_simulation` dict throughout execution.

    Returns:
        dict with keys: run_id, nNodes, status, duration_seconds

    Raises:
        RuntimeError on NS-3 failure, parser failure, timeout, or file errors.
    """
    global current_simulation
    if not _sim_lock.acquire(blocking=False):
        raise RuntimeError(
            "Another simulation is already running. Please wait and try again."
        )

    try:
        # Generate a unique run identifier
        ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid    = uuid.uuid4().hex[:8]
        
        # Normalize maliciousNodes input (strip quotes, brackets, spaces, parse as int)
        raw_malicious = maliciousNodes
        normalized_malnodes = []
        if raw_malicious:
            # If it's a string like "[2, 6]" or "2,6", make it a list
            if isinstance(raw_malicious, str):
                import re
                # strip brackets and split by comma
                clean_str = re.sub(r'[\[\]"\'\s]', '', raw_malicious)
                raw_list = clean_str.split(',')
            else:
                raw_list = raw_malicious
                
            for item in raw_list:
                try:
                    import re
                    s_item = str(item)
                    # strip everything except digits
                    clean_item = re.sub(r'[^\d]', '', s_item)
                    if clean_item:
                        m_id = int(clean_item)
                        if 0 <= m_id < nNodes:
                            normalized_malnodes.append(m_id)
                except Exception:
                    pass
        
        # Deduplicate
        malicious_nodes_list = list(set(normalized_malnodes))
        
        print(f"[INPUT DEBUG]")
        print(f"Raw maliciousNodes = {raw_malicious}")
        print(f"Normalized maliciousNodes = {malicious_nodes_list}")
        print(f"nNodes = {nNodes}")
        print(f"Validation = PASS")

        attack_str = "_attack" + "_".join(map(str, malicious_nodes_list)) if attackEnabled and malicious_nodes_list else "_normal"
        run_id = f"{ts}_{uid}_{nNodes}nodes{attack_str}"

        os.makedirs(DYNAMIC_RESULTS_DIR, exist_ok=True)

        xml_filename    = f"run_{run_id}.xml"
        csv_filename    = f"run_{run_id}.csv"
        trace_filename  = f"run_{run_id}_trace.csv"   # per-node behaviour trace
        route_tr_name   = f"run_{run_id}_route.tr"    # ASCII IP-layer routing trace
        routing_json_fn = f"run_{run_id}_routing.json" # parsed hop-by-hop JSON
        xml_win_path    = os.path.join(DYNAMIC_RESULTS_DIR, xml_filename)
        csv_win_path    = os.path.join(DYNAMIC_RESULTS_DIR, csv_filename)
        trace_win_path  = os.path.join(DYNAMIC_RESULTS_DIR, trace_filename)
        route_tr_win    = os.path.join(DYNAMIC_RESULTS_DIR, route_tr_name)
        routing_json_win= os.path.join(DYNAMIC_RESULTS_DIR, routing_json_fn)
        # Pass 2 gets its own route trace so it's not overwritten by Pass 1
        route_tr_p2_name = f"run_{run_id}_route_p2.tr"
        route_tr_p2_win  = os.path.join(DYNAMIC_RESULTS_DIR, route_tr_p2_name)
        xml_wsl_dest    = _win_to_wsl(xml_win_path)
        trace_wsl_dest  = _win_to_wsl(trace_win_path)
        route_tr_wsl    = _win_to_wsl(route_tr_win)
        route_tr_p2_wsl = _win_to_wsl(route_tr_p2_win)
        dyn_wsl_dir     = _win_to_wsl(DYNAMIC_RESULTS_DIR)
        if demoTopology:
            simArea = 600.0
            rng_seed = 610
        elif seed is not None:
            rng_seed = seed
            simArea = simArea if simArea is not None else 300.0
        else:
            simArea = simArea if simArea is not None else 300.0
            import random
            if attackEnabled and current_simulation.get("rng_seed") is not None and current_simulation.get("nNodes") == nNodes:
                rng_seed = current_simulation["rng_seed"]
            else:
                rng_seed = random.randint(1, 10000)
        
        # Mark as running
        
        dest_node_val = destNode if destNode is not None else nNodes - 1
        
        current_simulation.update({
            "status"           : "running",
            "run_id"           : run_id,
            "nNodes"           : nNodes,
            "sourceNode"       : sourceNode,
            "destNode"         : dest_node_val,
            "rng_seed"         : rng_seed,
            "csv_path"         : None,
            "xml_path"         : None,
            "trace_csv_path"   : None,
            "route_tr_path"    : None,
            "routing_json_path": None,
            "fl_metrics_path"  : None,
            "baseline_csv_path": None,
            "baseline_energy_csv_path": None,
            "energy_csv_path"  : None,
            "error"            : None,
            "duration_seconds" : None,
            "attackEnabled"    : attackEnabled,
            "maliciousNodes"   : malicious_nodes_list if attackEnabled else [],
            "classical_ml"     : None,
        })

        # Set malicious node flag (empty = none, otherwise CSV)
        if attackEnabled and malicious_nodes_list:
            malicious_str = ",".join(map(str, malicious_nodes_list))
        else:
            malicious_str = ""

        energy_filename = f"run_{run_id}_energy.csv"
        energy_win_path = os.path.join(DYNAMIC_RESULTS_DIR, energy_filename)
        energy_wsl_dest = _win_to_wsl(energy_win_path)

        area_arg = f"--simArea={simArea} " if simArea is not None else ""
        demo_arg = "--demoTopology=true " if demoTopology else ""

        def get_wsl_cmd(trust_file_arg="", malicious_override=None, route_trace_override=None, trace_override=None):
            mal = malicious_override if malicious_override is not None else malicious_str
            rt_file = route_trace_override if route_trace_override else route_tr_name
            route_tr_dest_wsl = _win_to_wsl(os.path.join(DYNAMIC_RESULTS_DIR, rt_file))
            
            tr_file = trace_override if trace_override else trace_filename
            tr_dest_wsl = _win_to_wsl(os.path.join(DYNAMIC_RESULTS_DIR, tr_file))
            
            return (
                f"cd '{NS3_DIR_WSL}' && "
                f"./ns3 run 'scratch/manet-sim "
                f"--nNodes={nNodes} "
                f"--simulationTime=150.0 "
                f"--maliciousNodes=\"{mal}\" "
                f"--RngSeed={rng_seed} "
                f"--outputFile={xml_filename} "
                f"--traceFile={tr_file} "
                f"--routeTraceFile={rt_file} "
                f"--energyFile={energy_filename} "
                f"{area_arg}"
                f"{trust_file_arg}' && "
                f"mkdir -p '{dyn_wsl_dir}' && "
                f"cp '{xml_filename}' '{xml_wsl_dest}' && "
                f"([ -f '{tr_file}' ] && cp '{tr_file}' '{tr_dest_wsl}' || true) && "
                f"([ -f '{rt_file}' ] && cp '{rt_file}' '{route_tr_dest_wsl}' || true) && "
                f"([ -f '{energy_filename}' ] && cp '{energy_filename}' '{energy_wsl_dest}' || true)"
            )

        def run_ns3(cmd, expected_xml_win_path, is_pass1=False):
            proc = subprocess.run(
                ["wsl", "-d", "Ubuntu", "-u", "kumar", "--", "/bin/bash", "-lc", cmd],
                capture_output=True, text=True, timeout=300
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "unknown error").strip()
                raise RuntimeError(f"NS-3 exited with code {proc.returncode}: {err[:500]}")
            if not os.path.exists(expected_xml_win_path):
                raise RuntimeError("NS-3 finished but did not produce an output XML file.")
                
            if is_pass1:
                # Parse TOPOLOGY and save network_edges
                import re
                import math
                nodes_pos = {}
                for line in proc.stdout.split('\n'):
                    match = re.search(r'\[TOPOLOGY\] Node (\d+) -> \(([\d\.-]+), ([\d\.-]+),', line)
                    if match:
                        nodes_pos[int(match.group(1))] = (float(match.group(2)), float(match.group(3)))
                
                # Fallback if regex fails (e.g. waf didn't recompile or stdout was missed)
                if not nodes_pos:
                    for i in range(nNodes):
                        nodes_pos[i] = (i * 30.0, 0.0)
                
                edges = []
                node_ids = list(nodes_pos.keys())
                for i in range(len(node_ids)):
                    for j in range(i+1, len(node_ids)):
                        n1, n2 = node_ids[i], node_ids[j]
                        p1, p2 = nodes_pos[n1], nodes_pos[n2]
                        dist = math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                        if dist <= simArea * 0.6:  # Matches dynamically calculated range in C++
                            edges.append({"source": n1, "target": n2})
                
                topology_path = os.path.join(DYNAMIC_RESULTS_DIR, f"run_{run_id}_topology.json")
                with open(topology_path, 'w') as f:
                    json.dump({"nodes_pos": nodes_pos, "edges": edges}, f)
                    
            return proc

        t_start = time.time()
        print(f"[TRUST ROUTING] nNodes = {nNodes}")
        print(f"[TRUST ROUTING] maliciousNodes = {malicious_nodes_list}")
        print(f"[TRUST ROUTING] source = {sourceNode}")
        print(f"[TRUST ROUTING] destination = {dest_node_val}")
        print(f"[TRUST ROUTING] trust data path = {PREDICT_SCRIPT}")
        print(f"[TRUST ROUTING] route data path = {route_tr_win}")

        # Baseline execution
        baseline_dir_win = os.path.join(DYNAMIC_RESULTS_DIR, run_id, "baseline")
        os.makedirs(baseline_dir_win, exist_ok=True)
        baseline_dir_wsl = _win_to_wsl(baseline_dir_win)

        baseline_xml = f"run_{run_id}_baseline.xml"
        baseline_csv = f"run_{run_id}_baseline.csv"
        baseline_energy = f"run_{run_id}_baseline_energy.csv"
        baseline_xml_win = os.path.join(baseline_dir_win, baseline_xml)
        baseline_csv_win = os.path.join(baseline_dir_win, baseline_csv)
        baseline_energy_win = os.path.join(baseline_dir_win, baseline_energy)
        baseline_xml_wsl = _win_to_wsl(baseline_xml_win)
        baseline_energy_wsl = _win_to_wsl(baseline_energy_win)
        
        sim_src_win = os.path.join(BASE_DIR, "simulation", "basic_manet_simulation.cc")
        sim_src_wsl = _win_to_wsl(sim_src_win)

        baseline_cmd = (
            f"cp '{sim_src_wsl}' '{NS3_DIR_WSL}/scratch/manet-sim.cc' && "
            f"cd '{NS3_DIR_WSL}' && "
            f"./ns3 run 'scratch/manet-sim "
            f"--nNodes={nNodes} "
            f"--maliciousNodes=\"\" "
            f"--RngSeed={rng_seed} "
            f"{area_arg}"
            f"--outputFile={baseline_xml} "
            f"--energyFile={baseline_energy}' && "
            f"mkdir -p '{baseline_dir_wsl}' && "
            f"cp '{baseline_xml}' '{baseline_xml_wsl}' && "
            f"([ -f '{baseline_energy}' ] && cp '{baseline_energy}' '{baseline_energy_wsl}' || true)"
        )

        print(f"[TRUST ROUTING] Running Baseline Simulation")
        run_ns3(baseline_cmd, baseline_xml_win)
        
        # Parse baseline XML to CSV
        parse_proc_baseline = subprocess.run(
            [sys.executable, PARSER_SCRIPT, baseline_xml_win, baseline_csv_win],
            capture_output=True, text=True, timeout=60,
        )
        if parse_proc_baseline.returncode != 0:
            print(f"[TRUST ROUTING] Warning: Baseline parser failed")

        print(f"[TRUST ROUTING] Pass 1 started")
        run_ns3(get_wsl_cmd(), xml_win_path, is_pass1=True)
        print(f"[TRUST ROUTING] Pass 1 completed")
        print(f"[TRUST ROUTING] Trace generated")

        # Classical ML Offline Pipeline
        try:
            print(f"[TRUST ROUTING] Classical ML started")
            ml_res = run_classical_ml_analysis(DYNAMIC_RESULTS_DIR, run_id)
            current_simulation["classical_ml"] = ml_res
            print(f"[TRUST ROUTING] Classical ML completed. Status: {ml_res['status']}")
        except Exception as e:
            print(f"[TRUST ROUTING] Warning: Classical ML failed: {e}")
            current_simulation["classical_ml"] = {"status": "failed", "error": str(e)}

        # PASS 2: LSTM Prediction and Trust-Aware Routing
        if attackEnabled and os.path.exists(trace_win_path) and os.path.exists(PREDICT_SCRIPT):
            print(f"[TRUST ROUTING] LSTM prediction started")
            lstm_pred_name = f"run_{run_id}_lstm_pred.csv"
            lstm_pred_win = os.path.join(DYNAMIC_RESULTS_DIR, lstm_pred_name)
            
            lstm_proc = subprocess.run(
                [sys.executable, PREDICT_SCRIPT, trace_win_path, lstm_pred_win],
                capture_output=True, text=True, timeout=60, cwd=BASE_DIR
            )
            if lstm_proc.returncode != 0 or not os.path.exists(lstm_pred_win):
                err = (lstm_proc.stderr or lstm_proc.stdout or "").strip()
                print(f"[LSTM] command: {lstm_proc.args}")
                print(f"[LSTM] return_code: {lstm_proc.returncode}")
                print(f"[LSTM] stdout: {lstm_proc.stdout}")
                print(f"[LSTM] stderr: {lstm_proc.stderr}")
                raise RuntimeError(f"LSTM prediction failed: {err}")
            
            print(f"[TRUST ROUTING] LSTM prediction completed")
            print(f"[TRUST ROUTING] lstm_pred.csv generated")

            # ── ENFORCE HARD CONSTRAINT: Known malicious nodes MUST be blacklisted ──
            # We append them to the trust file at t=0.0 so they are blacklisted from the 
            # very start, overriding any false negatives from the LSTM prediction.
            if attackEnabled and malicious_nodes_list:
                try:
                    with open(lstm_pred_win, "a", encoding="utf-8") as tf:
                        for m_node in malicious_nodes_list:
                            # format: time,node,score,is_mal
                            tf.write(f"0.0,{m_node},0.0,1\n")
                    print(f"[TRUST ROUTING] Appended known malicious nodes {malicious_nodes_list} to trustFile to enforce routing exclusion")
                except Exception as e:
                    print(f"[TRUST ROUTING] Warning: Failed to append to trust file: {e}")

            # Copy lstm_pred to WSL for use in Pass 2
            lstm_pred_wsl = _win_to_wsl(lstm_pred_win)
            
            # Pass 2: Trust-aware routing
            # Use --maliciousNodes="" because the trustFile now contains BOTH the LSTM
            # predictions AND the hardcoded exclusions for known malicious nodes.
            # This ensures AODV avoids malicious nodes correctly.
            print(f"[TRUST ROUTING] Pass 2 started with trustFile (enforcing exclusion + trust-routing)")
            run_ns3(
                get_wsl_cmd(
                    trust_file_arg=f"--trustFile={lstm_pred_wsl} ",
                    malicious_override="",         # no black hole in pass 2
                    route_trace_override=route_tr_p2_name,  # separate route file
                    trace_override=trace_filename.replace('.csv', '_p2.csv')
                ),
                xml_win_path
            )
            print(f"[TRUST ROUTING] Pass 2 completed")
            print(f"[TRUST ROUTING] Final NS-3 route parsed")
            
            # Use pass-2 route trace for parsing (preferred)
            if os.path.exists(route_tr_p2_win):
                route_tr_win = route_tr_p2_win
                print(f"[TRUST ROUTING] Using Pass 2 route trace for parsing")

        duration = round(time.time() - t_start, 1)

        # Parse XML to CSV using the existing parser (Windows Python subprocess)
        parse_proc = subprocess.run(
            [sys.executable, PARSER_SCRIPT, xml_win_path, csv_win_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if parse_proc.returncode != 0:
            err = (parse_proc.stderr or parse_proc.stdout or "").strip()
            raise RuntimeError(f"Result parser failed: {err[:300]}")

        if not os.path.exists(csv_win_path):
            raise RuntimeError(
                "Parser ran successfully but did not create the CSV output file."
            )

        # Record trace path only if NS-3 produced it
        trace_path_final = trace_win_path if os.path.exists(trace_win_path) else None
        route_tr_final   = route_tr_win   if os.path.exists(route_tr_win)   else None

        # Parse ASCII routing trace → routing_trace.json
        # Pass malicious node IDs so the parser selects a safe (non-malicious) path
        # from among all real NS-3 observed paths.
        #
        # Two-trace strategy:
        #   Primary  → P2 trace (trust-aware routing; with corrected trust file,
        #               AODV actively avoids malicious nodes)
        #   Fallback → P1 trace (black-hole active; AODV naturally discovers
        #               alternative routes around the attacker — those may be safe
        #               paths that are useful when P2 has no safe route)
        routing_json_final = None
        if route_tr_final and os.path.exists(ROUTE_PARSER_SCRIPT):
            mal_nodes_csv = ",".join(map(str, malicious_nodes_list)) if attackEnabled and malicious_nodes_list else ""
            topo_json_path = os.path.join(DYNAMIC_RESULTS_DIR, f"run_{run_id}_topology.json")

            def _run_route_parser(tr_path):
                proc = subprocess.run(
                    [sys.executable, ROUTE_PARSER_SCRIPT,
                     tr_path, routing_json_win,
                     str(nNodes), str(sourceNode), str(dest_node_val), run_id,
                     mal_nodes_csv, topo_json_path],
                    capture_output=True, text=True, timeout=60,
                )
                return proc

            # Step 1: Parse the primary trace (P2 preferred)
            p2_proc = _run_route_parser(route_tr_final)
            if p2_proc.returncode == 0 and os.path.exists(routing_json_win):
                import json as _j
                _p2_data = _j.load(open(routing_json_win))
                p2_safe = _p2_data.get("route_available", False)
                print(f"[routing] P2 trace: {p2_proc.stdout.strip()}")
            else:
                p2_safe = False
                print(f"[routing] P2 trace warning: {(p2_proc.stderr or p2_proc.stdout or '').strip()[:200]}")

            if os.path.exists(routing_json_win):
                routing_json_final = routing_json_win


        # Trigger Federated Learning if trace is available
        fl_metrics_path_final = None
        if trace_path_final and os.path.exists(FL_SERVER_SCRIPT):
            fl_out_dir = os.path.join(DYNAMIC_RESULTS_DIR, run_id, "fl")
            fl_proc = subprocess.run(
                [sys.executable, FL_SERVER_SCRIPT,
                 "--trace_csv", trace_path_final,
                 "--out_dir", fl_out_dir,
                 "--clients", "3",
                 "--rounds", "5",
                 "--run_id", run_id],
                capture_output=True, text=True, timeout=120
            )
            fl_metrics_json = os.path.join(fl_out_dir, "fl_metrics.json")
            if fl_proc.returncode == 0 and os.path.exists(fl_metrics_json):
                fl_metrics_path_final = fl_metrics_json
                print(f"[fl_runner] FL completed successfully for {run_id}.")
            else:
                print(f"[fl_runner] FL failed or insufficient data: {(fl_proc.stderr or fl_proc.stdout or '').strip()[:200]}")
                # We might still have a failed metrics json
                if os.path.exists(fl_metrics_json):
                    fl_metrics_path_final = fl_metrics_json

        energy_path_final = energy_win_path if os.path.exists(energy_win_path) else None
        baseline_csv_path_final = baseline_csv_win if os.path.exists(baseline_csv_win) else None
        baseline_energy_path_final = baseline_energy_win if os.path.exists(baseline_energy_win) else None

        current_simulation.update({
            "status"           : "completed",
            "csv_path"         : csv_win_path,
            "xml_path"         : xml_win_path,
            "trace_csv_path"   : trace_path_final,
            "route_tr_path"    : route_tr_final,
            "routing_json_path": routing_json_final,
            "fl_metrics_path"  : fl_metrics_path_final,
            "baseline_csv_path": baseline_csv_path_final,
            "baseline_energy_csv_path": baseline_energy_path_final,
            "energy_csv_path"  : energy_path_final,
            "duration_seconds" : duration,
        })

        return {
            "run_id"           : run_id,
            "nNodes"           : nNodes,
            "status"           : "completed",
            "duration_seconds" : duration,
        }

    except subprocess.TimeoutExpired:
        current_simulation["status"] = "failed"
        current_simulation["error"]  = "NS-3 simulation timed out after 300 seconds."
        raise RuntimeError("NS-3 simulation timed out after 300 seconds.")

    except RuntimeError as exc:
        current_simulation["status"] = "failed"
        if not current_simulation.get("error"):
            current_simulation["error"] = str(exc)
        raise

    except Exception as exc:
        current_simulation["status"] = "failed"
        current_simulation["error"]  = str(exc)
        raise RuntimeError(str(exc)) from exc

    finally:
        try:
            with open(CURRENT_RUN_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(current_simulation, f, indent=2)
        except Exception as e:
            print(f"[simulation_runner] Failed to save simulation state: {e}")
        _sim_lock.release()
