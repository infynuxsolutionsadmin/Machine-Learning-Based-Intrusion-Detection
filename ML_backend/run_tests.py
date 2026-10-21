import urllib.request, json, time

tests = [
    {"nNodes": 8, "scenario": "attack", "attackerNode": 6, "name": "TEST 1"},
    {"nNodes": 8, "scenario": "attack", "attackerNode": 4, "name": "TEST 2"},
    {"nNodes": 10, "scenario": "attack", "attackerNode": 6, "name": "TEST 3"},
]

for t in tests:
    print(f"\nRunning {t['name']}...")
    req_data = json.dumps({
        "scenario": t["scenario"],
        "attackerNode": t["attackerNode"],
        "nNodes": t["nNodes"],
        "runId": "test-" + str(time.time())
    }).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:8000/api/simulation/run', data=req_data, headers={'Content-Type':'application/json'})
    
    try:
        resp = json.loads(urllib.request.urlopen(req).read().decode())
        print(f"Simulation completed. Fetching routing path...")
        
        path_req = urllib.request.Request('http://127.0.0.1:8000/api/routing/path')
        path_resp = json.loads(urllib.request.urlopen(path_req).read().decode())
        
        if path_resp.get('route_available'):
            hops = path_resp.get('hops', [])
            path_str = " -> ".join([f"Node {h['node_id']}" for h in hops])
            print(f"Route: {path_str}")
        else:
            print("Route: Actual route unavailable")
            
    except Exception as e:
        print(f"Error: {e}")
