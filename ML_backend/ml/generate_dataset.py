import os
import subprocess
import pandas as pd
import random

NS3_DIR = "/home/kumar/MANET/ns-3/ns-allinone-3.41/ns-3.41"
DATASET_PATH = "trust_dataset.csv"

def run_simulation(seed, malicious_node):
    trace_file = f"trace_seed{seed}.csv"
    cmd = [
        "wsl", "-e", "bash", "-lc",
        f"cd {NS3_DIR} && ./ns3 run 'scratch/manet-sim/manet-sim "
        f"--numNodes=8 --simulationTime=60.0 --maliciousNode={malicious_node} "
        f"--RngSeed={seed} --traceFile={trace_file}'"
    ]
    print(f"Running Seed {seed} | Malicious Node: {malicious_node}")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    copy_cmd = ["wsl", "-e", "bash", "-lc", f"cp {NS3_DIR}/{trace_file} /mnt/c/Users/divya/OneDrive/Desktop/MANET/manet-backend/ml/{trace_file}"]
    subprocess.run(copy_cmd)
    
    local_trace = f"c:/Users/divya/OneDrive/Desktop/MANET/manet-backend/ml/{trace_file}"
    if os.path.exists(local_trace):
        df = pd.read_csv(local_trace)
        df['run_id'] = seed
        return df
    return None

def main():
    print("Generating Trust Dataset...")
    all_data = []
    
    # Generate 10 simulation runs
    # 5 with no attacker, 5 with an attacker at a random node (1-6 to avoid source 0 and dest 7)
    for seed in range(1, 11):
        if seed <= 5:
            malicious_node = 255 # No attacker
        else:
            malicious_node = random.randint(1, 6) # Random attacker node
            
        df = run_simulation(seed, malicious_node)
        if df is not None:
            all_data.append(df)
            
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        final_df.to_csv(DATASET_PATH, index=False)
        print(f"Dataset generated at {DATASET_PATH} with {len(final_df)} records.")
    else:
        print("Failed to generate dataset.")

if __name__ == "__main__":
    main()
