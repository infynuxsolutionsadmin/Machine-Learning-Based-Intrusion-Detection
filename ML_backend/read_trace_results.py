import pandas as pd
import json
import urllib.request
import os

run_id = '20260925_185904_2b3b0c7a_8nodes_attack2_5'
res_dir = r'c:\Users\divya\OneDrive\Desktop\Final year_ppt-2026\Vijay_Batch\MANET\manet-backend\simulation\results\dynamic'
p1_path = os.path.join(res_dir, f'run_{run_id}_trace.csv')
p2_path = os.path.join(res_dir, f'run_{run_id}_trace_p2.csv')
routing_path = os.path.join(res_dir, f'run_{run_id}_routing.json')

print('--- PASS 1 TRACE ---')
if os.path.exists(p1_path):
    df1 = pd.read_csv(p1_path)
    for n in [2,5]:
        rows = df1[df1['node']==n]
        if not rows.empty:
            max_rx = rows['rx'].max()
            max_fw = rows['fw'].max()
            max_drop = rows['drop'].max()
            labels = rows['label'].unique().tolist()
            print(f'Node {n}: rx={max_rx}, fw={max_fw}, drop={max_drop}, labels={labels}')
else:
    print('Pass 1 trace missing!')

print('\n--- PASS 2 TRACE ---')
if os.path.exists(p2_path):
    print(f'Pass 2 file exists: {p2_path}')
    df2 = pd.read_csv(p2_path)
    for n in [2,5]:
        rows = df2[df2['node']==n]
        if not rows.empty:
            max_rx = rows['rx'].max()
            max_fw = rows['fw'].max()
            max_drop = rows['drop'].max()
            labels = rows['label'].unique().tolist()
            print(f'Node {n}: rx={max_rx}, fw={max_fw}, drop={max_drop}, labels={labels}')
else:
    print('Pass 2 trace missing!')

print('\n--- API PREDICTIONS ---')
req = urllib.request.Request('http://127.0.0.1:8000/api/trust/dynamic')
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        nodes_data = data.get('nodes', [])
        for nd in nodes_data:
            if nd['node'] in [2,5]:
                print(f"Node {nd['node']}: trust={nd['predicted_trust_score']}, predicted_malicious={nd['predicted_malicious']}")
except Exception as e:
    print('API error:', e)

print('\n--- ROUTING ---')
if os.path.exists(routing_path):
    with open(routing_path, 'r') as f:
        r_data = json.load(f)
        hops = r_data.get('hops', [])
        if hops:
            route = ' -> '.join([str(h['node_id']) for h in hops])
            print(f'Route: {route}')
            print(f"Contains 2 or 5: {any(h['node_id'] in [2,5] for h in hops)}")
        else:
            print('No route found in json.')
else:
    print('Routing json missing!')
