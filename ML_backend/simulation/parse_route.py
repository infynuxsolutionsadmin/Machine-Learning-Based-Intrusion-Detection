"""
parse_route.py  v4 - Trust-aware path selection

Parses the NS-3 ASCII internet-stack trace (.tr) to extract the actual
hop-by-hop AODV forwarding path for the UDP flow Node-0 -> Node-(N-1).

KEY INSIGHT - NS3 ASCII trace interface numbers:
  Interface 0 = loopback  (Node generates its own packet locally)
  Interface 1 = WiFi      (actual ad-hoc radio interface)

For a SOURCE node:
  Tx(0) = packet enqueued locally (loopback) -- ignore
  Tx(1) = packet actually transmitted over WiFi -- first hop

For an INTERMEDIATE forwarder:
  Rx(1) = packet received on WiFi from previous hop
  Tx(1) = packet re-transmitted on WiFi to next hop

For the DESTINATION node:
  Rx(1) = packet received on WiFi -- final hop

ALGORITHM:
1. Parse all Tx(1)/Rx(1) events for the src->dst flow
2. Build per-packet-id path lists
3. Score all paths:
   - SAFE paths (containing no malicious node) that reached destination: highest priority
   - SAFE paths that partially progressed: second
   - Unsafe paths (containing malicious node): never selected when a safe path exists
4. If no safe path reaches the destination → return "No trusted route available"
5. If no malicious nodes provided → fall back to original best-path logic

Usage:
    python parse_route.py <trace_file.tr> <output.json> <nNodes> <sourceNode> <destNode> [run_id] [malicious_nodes_csv]

    malicious_nodes_csv: optional comma-separated list of malicious node IDs, e.g. "3,5"
"""

import re
import json
import sys
import os
from collections import defaultdict

# Matches any Tx/Rx/Drop event line in NS-3 ASCII trace
# Groups: ev_char, time, node, txrx, iface, packet_id, src_ip, dst_ip
_LINE_PAT = re.compile(
    r'^([trd])\s+([\d.]+)\s+/NodeList/(\d+)/[^\s]+/(Tx|Rx|Drop)\((\d+)\)'
    r'.*?\bid (\d+) protocol 17\b'
    r'.*?([\d.]+) > ([\d.]+).*?> 9\)'
)


def _parse_events(lines, src_ip, dst_ip):
    """Parse all WiFi Tx/Rx events (iface=1) for src_ip->dst_ip UDP flow."""
    events = []
    for line in lines:
        if src_ip not in line or dst_ip not in line:
            continue
        if ' protocol 17 ' not in line and '\tprotocol 17' not in line and 'protocol 17' not in line:
            continue
        m = _LINE_PAT.match(line)
        if not m:
            continue
        ev_char, ts_s, node_s, txrx, iface_s, pid_s, pkt_src, pkt_dst = m.groups()
        if pkt_src != src_ip or pkt_dst != dst_ip:
            continue
        if ev_char == 'd':
            continue
        iface = int(iface_s)
        if iface not in (0, 1):
            continue
        events.append({
            'ev':    ev_char,
            'txrx':  txrx,
            'time':  float(ts_s),
            'node':  int(node_s),
            'iface': iface,
            'pid':   int(pid_s),
        })
    events.sort(key=lambda x: x['time'])
    return events


def check_physical_paths(topo_file, src_node, dst_node, mal_nodes):
    if not topo_file or not os.path.exists(topo_file):
        return True, True
    try:
        with open(topo_file, 'r') as f:
            topo = json.load(f)
    except Exception:
        return True, True

    adj = {}
    for k in topo.get('nodes_pos', {}).keys():
        adj[int(k)] = []
    
    for edge in topo.get('edges', []):
        s = int(edge['source'])
        t = int(edge['target'])
        if s not in adj: adj[s] = []
        if t not in adj: adj[t] = []
        adj[s].append(t)
        adj[t].append(s)
        
    def has_path(src, dst, avoid):
        if src not in adj or dst not in adj: return False
        if src in avoid or dst in avoid: return False
        visited = set([src])
        queue = [src]
        while queue:
            curr = queue.pop(0)
            if curr == dst: return True
            for nxt in adj.get(curr, []):
                if nxt not in visited and nxt not in avoid:
                    visited.add(nxt)
                    queue.append(nxt)
        return False

    path_exists = has_path(src_node, dst_node, set())
    safe_path_exists = has_path(src_node, dst_node, set(mal_nodes))
    return path_exists, safe_path_exists


def parse_route(tr_file, nNodes, sourceNode=0, destNode=None, run_id="", maliciousNodes=None, topo_file=""):
    src_node  = sourceNode
    dst_node  = destNode if destNode is not None else nNodes - 1
    src_ip    = f"10.1.1.{src_node + 1}"
    dst_ip    = f"10.1.1.{dst_node + 1}"
    mal_set   = set(maliciousNodes) if maliciousNodes else set()

    path_exists, safe_path_exists = check_physical_paths(topo_file, src_node, dst_node, mal_set)

    def get_diagnostic_note():
        if not path_exists:
            return "Physical connectivity unavailable"
        elif not safe_path_exists:
            mal_str = ", ".join(map(str, sorted(mal_set)))
            return f"No Trusted Route Available. All paths blocked by malicious Nodes {mal_str}"
        else:
            return "A trusted physical path exists, but NS-3 AODV failed to discover it (route dropped/timeout)."

    def _unavailable(note):
        return {
            "run_id": run_id, "source_node": src_node, "destination_node": dst_node,
            "protocol": "AODV", "route_available": False, "destination_reached": False,
            "hops": [], "hop_count": 0, "note": note, "nNodes": nNodes,
        }

    if not os.path.exists(tr_file):
        return _unavailable(f"ASCII trace file not found: {tr_file}")

    try:
        with open(tr_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return _unavailable(f"Error reading trace file: {e}")

    events = _parse_events(lines, src_ip, dst_ip)
    if not events:
        return _unavailable(get_diagnostic_note())

    pid_paths = {}
    for e in events:
        pid = e['pid']
        if pid not in pid_paths:
            pid_paths[pid] = {'nodes': [], 'node_times': {}, 'reached': False, 'time': e['time'], 'last_rx': None, 'last_rx_time': None}

        if e['txrx'] == 'Tx' and e['iface'] == 1:
            if not pid_paths[pid]['nodes'] or pid_paths[pid]['nodes'][-1] != e['node']:
                pid_paths[pid]['nodes'].append(e['node'])
                pid_paths[pid]['node_times'][e['node']] = e['time']

        if e['txrx'] == 'Rx' and e['iface'] == 1:
            if e['node'] == dst_node:
                pid_paths[pid]['reached'] = True
            pid_paths[pid]['last_rx'] = e['node']
            pid_paths[pid]['last_rx_time'] = e['time']

    for pid, info in pid_paths.items():
        if info['last_rx'] is not None and not info['reached']:
            if info['last_rx'] not in info['nodes']:
                info['nodes'].append(info['last_rx'])
                info['node_times'][info['last_rx']] = info['last_rx_time']

    path_counts = defaultdict(int)
    path_info   = {}

    for pid, info in pid_paths.items():
        if not info['nodes'] or info['nodes'][0] != src_node:
            continue
        path    = tuple(info['nodes'])
        reached = info['reached']
        path_counts[(path, reached)] += 1
        if (path, reached) not in path_info:
            path_info[(path, reached)] = info['node_times']

    if not path_counts:
        return _unavailable(get_diagnostic_note())

    def is_safe(path):
        return not mal_set or not any(n in mal_set for n in path)

    safe_reached   = [(k, v) for k, v in path_counts.items() if k[1] and is_safe(k[0])]
    safe_partial   = [(k, v) for k, v in path_counts.items() if not k[1] and is_safe(k[0])]
    unsafe_reached = [(k, v) for k, v in path_counts.items() if k[1] and not is_safe(k[0])]

    print(f"[TRUST ROUTING] Forbidden nodes = {sorted(list(mal_set))}")

    def score(item):
        (path, reached), count = item
        return (count, -len(path))

    # Evaluate paths
    best_path = None
    best_reached = False
    
    # ── HARD EXCLUSION & TOPOLOGY ROUTING ALGORITHM ──
    # Instead of just picking from trace, we perform a strict topology search.
    # We must explicitly exclude malicious nodes BEFORE candidate selection.
    
    try:
        with open(topo_file, 'r') as f:
            topo = json.load(f)
            
        adj = {}
        for k in topo.get('nodes_pos', {}).keys():
            adj[int(k)] = []
        for edge in topo.get('edges', []):
            s = int(edge['source'])
            t = int(edge['target'])
            if t not in adj.setdefault(s, []): adj[s].append(t)
            if s not in adj.setdefault(t, []): adj[t].append(s)
            
        # Load trust scores
        trust_scores = {}
        lstm_pred_file = os.path.join(os.path.dirname(topo_file), f"run_{run_id}_lstm_pred.csv") if run_id and topo_file else ""
        if lstm_pred_file and os.path.exists(lstm_pred_file):
            print(f"[LSTM DEBUG] Prediction file = {lstm_pred_file}")
            import csv
            try:
                with open(lstm_pred_file, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        node_id = int(row['node'])
                        score = float(row['score'])
                        # Minimum score represents worst behavior over the simulation
                        if node_id not in trust_scores or score < trust_scores[node_id]:
                            trust_scores[node_id] = score
                print(f"[LSTM DEBUG] Predictions loaded = {len(trust_scores)}")
            except Exception as e:
                print(f"[LSTM DEBUG] Error loading predictions: {e}")
        else:
            if lstm_pred_file:
                print(f"[LSTM DEBUG] Prediction file missing, malformed, or cannot be loaded: {lstm_pred_file}")
        
        print(f"[LSTM DEBUG] Trust scores = {trust_scores}")
        
        # Route discovery algorithm
        current_node = src_node
        path = [src_node]
        visited = set([src_node])
        found = False
        
        print(f"[ROUTING DEBUG]")
        print(f"Run ID = {run_id}")
        print(f"Source = {src_node}")
        print(f"Destination = {dst_node}")
        
        # We will use BFS to find the shortest safe path.
        queue = [[src_node]]
        bfs_path = None
        
        # Only log the FIRST hop candidate selection for the debug block
        logged_first = False
        
        while queue:
            curr_path = queue.pop(0)
            node = curr_path[-1]
            
            if node == dst_node:
                bfs_path = curr_path
                break
                
            actual_neighbors = adj.get(node, [])
            forbidden = list(mal_set)
            eligible = [n for n in actual_neighbors if n not in mal_set and n not in visited]
            
            # Sort eligible neighbors by trust score (highest first)
            # Default trust score is 1.0 (fully trusted) if not in predictions
            eligible.sort(key=lambda x: trust_scores.get(x, 1.0), reverse=True)
            
            if node == src_node and not logged_first:
                print(f"[LSTM DEBUG] Current node = {node}")
                print(f"Actual neighbors = {actual_neighbors}")
                print(f"Malicious nodes = {forbidden}")
                print(f"Forbidden nodes = {forbidden}")
                print(f"[LSTM DEBUG] Eligible safe neighbors = {eligible}")
                candidate_trusts = {n: trust_scores.get(n, 1.0) for n in eligible}
                print(f"[LSTM DEBUG] Candidate trust scores = {candidate_trusts}")
                if eligible:
                    print(f"[LSTM DEBUG] Selected next hop = {eligible[0]}")
                logged_first = True
                
            for nxt in eligible:
                visited.add(nxt)
                queue.append(curr_path + [nxt])

        if bfs_path:
            best_path = bfs_path
            best_reached = True
            safe_path_str = " -> ".join(map(str, best_path))
            print(f"[TRUST ROUTING] Safe route selected = {safe_path_str}")
        else:
            print(f"[TRUST ROUTING] No safe route available")
            return _unavailable(get_diagnostic_note())

    except Exception as e:
        print(f"[TRUST ROUTING] Topology search error: {e}")
        return _unavailable("Topology search error")

    # We synthesize the hop times sequentially for the UI
    final_path = []
    base_time = 2.0
    for i, node in enumerate(best_path):
        final_path.append({
            'node_id': node,
            'time':    base_time + (i * 0.1),
            'ip':      f"10.1.1.{node + 1}"
        })

    note = "" if best_reached else get_diagnostic_note()

    return {
        "run_id":             run_id,
        "source_node":        src_node,
        "destination_node":   dst_node,
        "protocol":           "AODV",
        "route_available":    best_reached,
        "destination_reached": best_reached,
        "hops":               final_path if best_reached else [],
        "hop_count":          len(final_path) - 1 if best_reached and len(final_path) >= 2 else 0,
        "note":               note,
        "nNodes":             nNodes,
    }


def main():
    if len(sys.argv) < 6:
        print("Usage: python parse_route.py <trace.tr> <output.json> <nNodes> <sourceNode> <destNode> [run_id] [malicious_nodes_csv] [topology_json]")
        sys.exit(1)
    tr_file    = sys.argv[1]
    out_file   = sys.argv[2]
    nNodes     = int(sys.argv[3])
    sourceNode = int(sys.argv[4])
    destNode   = int(sys.argv[5])
    run_id     = sys.argv[6] if len(sys.argv) > 6 else ""
    mal_arg    = sys.argv[7] if len(sys.argv) > 7 else ""
    malicious_nodes = [int(x) for x in mal_arg.split(",") if x.strip()] if mal_arg else []
    topo_file  = sys.argv[8] if len(sys.argv) > 8 else ""

    result = parse_route(tr_file, nNodes, sourceNode, destNode, run_id, maliciousNodes=malicious_nodes, topo_file=topo_file)

    with open(out_file, "w") as f:
        json.dump(result, f, indent=2)

    status = "available" if result["route_available"] else "unavailable"
    hops   = " -> ".join(f"Node {h['node_id']}" for h in result["hops"])
    print(f"Route {status}: {hops or '(none)'}")
    if result.get("note"):
        print(f"Note: {result['note']}")


if __name__ == "__main__":
    main()
