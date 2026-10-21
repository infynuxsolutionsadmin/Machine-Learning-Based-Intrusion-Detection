import sys
import re
import csv
import json
sys.path.append('.')
from app.services.simulation_runner import run_simulation

drop_pat = re.compile(r'/NodeList/4/\$ns3::Ipv4L3Protocol/Drop\(1\).*10\.1\.1\.1 > 10\.1\.1\.8')

def get_metrics(run_id):
    csv_file = f'simulation/results/dynamic/run_{run_id}.csv'
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['flow_id'] == '1':
                return row
    return None

for seed in range(1, 100):
    print(f'Testing seed {seed}...')
    res_normal = run_simulation(8, attackEnabled=False, seed=seed)
    res_attack = run_simulation(8, attackEnabled=True, attackerNode=4, seed=seed)
    
    tr_file = f'simulation/results/dynamic/run_{res_attack["run_id"]}_route.tr'
    
    found_drop = False
    with open(tr_file, 'r') as f:
        for line in f:
            if drop_pat.search(line):
                found_drop = True
                break
                
    if found_drop:
        print(f'FOUND GOLDEN SEED: {seed}')
        m_norm = get_metrics(res_normal['run_id'])
        m_att = get_metrics(res_attack['run_id'])
        
        print('Normal Metrics:', m_norm)
        print('Attack Metrics:', m_att)
        print('Normal Run ID:', res_normal['run_id'])
        print('Attack Run ID:', res_attack['run_id'])
        break
