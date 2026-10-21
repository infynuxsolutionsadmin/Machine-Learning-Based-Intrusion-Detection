import os
import subprocess
import json
import sys

NS3_DIR = "/home/kumar/MANET/ns-3/ns-allinone-3.41/ns-3.41"
NS3_BIN = "build/scratch/manet-sim/ns3.41-manet-sim-default"

area = 600
for seed in range(1, 1000):
    print(f"Trying Area {area}, Seed {seed}...", flush=True)
    
    xml_wsl_dest = f"/mnt/c/Users/divya/OneDrive/Desktop/MANET/manet-backend/simulation/seed_test.xml"
    trace_wsl_dest = f"/mnt/c/Users/divya/OneDrive/Desktop/MANET/manet-backend/simulation/seed_test.csv"
    route_wsl_dest = f"/mnt/c/Users/divya/OneDrive/Desktop/MANET/manet-backend/simulation/seed_test.tr"
    energy_wsl_dest = f"/mnt/c/Users/divya/OneDrive/Desktop/MANET/manet-backend/simulation/seed_test_energy.csv"
    
    cmd = (
        f"wsl -d Ubuntu -u kumar -- bash -lc \"cd {NS3_DIR} && ./{NS3_BIN} "
        f"--nNodes=8 --maliciousNode=255 --RngSeed={seed} --simArea={area} "
        f"--outputFile='{xml_wsl_dest}' --traceFile='{trace_wsl_dest}' "
        f"--routeTraceFile='{route_wsl_dest}' --energyFile='{energy_wsl_dest}'\""
    )
    
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    parse_cmd = f"python parse_route.py seed_test.tr seed_route.json 8"
    subprocess.run(parse_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    try:
        if os.path.exists("seed_route.json"):
            with open("seed_route.json", "r") as f:
                data = json.load(f)
                hc = data.get("hop_count")
                reached = data.get("destination_reached")
                if hc == 4 and reached:
                    print(f"FOUND COMBINATION! Area: {area}, Seed: {seed} with route: {data.get('hops')}", flush=True)
                    sys.exit(0)
    except Exception:
        pass
