import requests
import time

BASE_URL = "http://localhost:8000/api"

tests = [
    {"nodes": 8, "source": 0, "destination": 7, "malicious": [2, 6]},
    {"nodes": 8, "source": 0, "destination": 7, "malicious": [4, 6]},
    {"nodes": 8, "source": 0, "destination": 7, "malicious": [5, 6]},
    {"nodes": 8, "source": 0, "destination": 7, "malicious": [1, 3, 7]},
]

for i, test in enumerate(tests, 1):
    print(f"\n--- Test {i} ---")
    payload = {
        "nNodes": test["nodes"],
        "sourceNode": test["source"],
        "destinationNode": test["destination"],
        "attackEnabled": True,
        "maliciousNodes": test["malicious"],
        "seed": 42
    }
    
    print(f"Running simulation with {payload}...")
    res = requests.post(f"{BASE_URL}/simulation/run", json=payload)
    print("Run response:", res.json())
    
    # Wait for completion
    while True:
        status_res = requests.get(f"{BASE_URL}/simulation/status")
        status = status_res.json()["status"]
        if status in ["completed", "failed"]:
            break
        time.sleep(1)
        
    print("Simulation completed.")
    
    # Fetch route
    route_res = requests.get(f"{BASE_URL}/routing/path")
    print("Route response:", route_res.json())
