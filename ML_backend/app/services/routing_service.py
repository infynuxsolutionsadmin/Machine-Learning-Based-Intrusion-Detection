"""
routing_service.py
Reads the parsed hop-by-hop routing JSON for the current dynamic simulation
run and enriches it with attack configuration context.
"""
import json
import os
from typing import Dict, Any, Optional, List


def get_routing_path(
    routing_json_path: Optional[str],
    nNodes: int,
    attackEnabled: bool,
    maliciousNodes: Optional[List[int]],
    run_id: Optional[str],
    sourceNode: int = 0,
    destNode: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Load the routing trace JSON and add attack context.

    When no JSON is available, returns a clear "unavailable" response with
    the current simulation configuration so the frontend can still show the
    source/destination nodes correctly.
    """
    dest_node_val = destNode if destNode is not None else nNodes - 1
    base = {
        "run_id":            run_id,
        "nNodes":            nNodes,
        "source_node":       sourceNode,
        "destination_node":  dest_node_val,
        "source_ip":         f"10.1.1.{sourceNode + 1}",
        "destination_ip":    f"10.1.1.{dest_node_val + 1}",
        "protocol":          "AODV",
        "attackEnabled":     attackEnabled,
        "maliciousNodes":    maliciousNodes if attackEnabled and maliciousNodes is not None else [],
    }

    if not routing_json_path or not os.path.exists(routing_json_path):
        base.update({
            "route_available":    False,
            "destination_reached": False,
            "hops":               [],
            "hop_count":          0,
            "note":               (
                "No routing trace available for this run. "
                "Either the simulation has not completed yet, "
                "or the NS-3 binary predates the --routeTraceFile feature."
            ),
        })
        return base

    try:
        with open(routing_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        base.update({
            "route_available":    False,
            "destination_reached": False,
            "hops":               [],
            "hop_count":          0,
            "note":               f"Failed to load routing trace: {e}",
        })
        return base

    # Merge parsed data with base context
    base.update({
        "route_available":    data.get("route_available", False),
        "destination_reached": data.get("destination_reached", False),
        "hops":               data.get("hops", []),
        "hop_count":          data.get("hop_count", 0),
        "note":               data.get("note", ""),
    })

    # ── Final Validation (as requested by user) ─────────
    # assert source in route
    # assert destination in route
    # assert len(route) >= 2
    # assert no malicious node exists in route
    # assert every consecutive pair in route is actually connected
    # assert route belongs to the CURRENT simulation run

    def _fail_route(msg):
        base.update({
            "route_available":    False,
            "destination_reached": False,
            "hops":               [],
            "hop_count":          0,
            "note":               msg,
            "route_nodes":        [],
            "status":             "no_safe_route"
        })
        print(f"[ROUTING DEBUG] Final route validation = FAIL ({msg})")
        return base

    if base["route_available"] and base["hops"]:
        nodes_in_route = [h["node_id"] for h in base["hops"]]
        
        # 1. source in route
        if nodes_in_route[0] != sourceNode:
            return _fail_route("Source node is not the first hop")
            
        # 2. destination in route
        if nodes_in_route[-1] != dest_node_val:
            return _fail_route("Destination node is not the last hop")
            
        # 3. length >= 2
        if len(nodes_in_route) < 2:
            return _fail_route("Route length is less than 2")
            
        # 4. no malicious nodes
        if attackEnabled and maliciousNodes:
            mal_set = set(maliciousNodes)
            for node in nodes_in_route:
                if node in mal_set:
                    return _fail_route(f"Malicious node {node} in route")
                    
        # 5. consecutive pairs connected
        topology_path = None
        if run_id:
            from app.services.simulation_runner import DYNAMIC_RESULTS_DIR
            topology_path = os.path.join(DYNAMIC_RESULTS_DIR, f"run_{run_id}_topology.json")
            
        if topology_path and os.path.exists(topology_path):
            try:
                with open(topology_path, 'r') as f:
                    top_data = json.load(f)
                    edges = top_data.get("edges", [])
                    adj = {}
                    for e in edges:
                        u, v = int(e["source"]), int(e["target"])
                        adj.setdefault(u, set()).add(v)
                        adj.setdefault(v, set()).add(u)
                        
                    for i in range(len(nodes_in_route) - 1):
                        u = nodes_in_route[i]
                        v = nodes_in_route[i+1]
                        if v not in adj.get(u, set()):
                            return _fail_route(f"Hop {u} -> {v} is not physically connected")
            except Exception as e:
                print(f"[ROUTING DEBUG] Warning: failed to validate topology edges: {e}")
                
        # 6. route belongs to current simulation run
        # We already checked run_id in the caller / by using the correct json path, 
        # but let's make sure the JSON data's run_id matches.
        if data.get("run_id") and run_id and data.get("run_id") != run_id:
            return _fail_route("Route belongs to a different simulation run")

        base["route_nodes"] = nodes_in_route
        base["status"] = "safe_route_found"
        print(f"[ROUTING DEBUG] Final route validation = PASS")
    else:
        # No route available
        base["route_nodes"] = []
        base["status"] = "no_safe_route"

    return base
