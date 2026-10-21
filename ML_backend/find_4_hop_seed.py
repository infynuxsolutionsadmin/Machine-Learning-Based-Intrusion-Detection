import sys
import json
import time
sys.path.append('.')
from app.services.simulation_runner import run_simulation, current_simulation

for seed in [610]:
    res_normal = run_simulation(8, attackEnabled=False, seed=seed, simArea=600.0)
    
    with open(current_simulation['routing_json_path'], 'r') as f:
        routing_data = json.load(f)
        
    print(f"Seed {seed}: {routing_data['hop_count']} hops")
    if routing_data['hop_count'] >= 4:
        print(f"FOUND 4-HOP SEED: {seed}")
        print(routing_data['hops'])
        break
