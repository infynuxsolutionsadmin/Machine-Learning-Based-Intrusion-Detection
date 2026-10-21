import json, math, re

# Load positions
with open('c:/Users/divya/OneDrive/Desktop/MANET/manet-backend/simulation/results/dynamic/run_20260917_125303_6b14f6a6_8nodes_attack3_topology.json') as f:
    data = json.load(f)
    nodes_pos = data['nodes_pos']

# Load trace and find actual successful Rx events
lines = open('c:/Users/divya/OneDrive/Desktop/MANET/manet-backend/simulation/results/dynamic/run_20260917_125303_6b14f6a6_8nodes_attack3_route_p2.tr').readlines()

max_dist = 0.0

for line in lines:
    if 'Rx' in line:
        rx_match = re.search(r'/NodeList/(\d+)/', line)
        if rx_match:
            rx_node = int(rx_match.group(1))
            tx_ip_match = re.search(r'10\.1\.1\.(\d+)', line)
            if tx_ip_match:
                tx_node = int(tx_ip_match.group(1)) - 1
                if str(tx_node) in nodes_pos and str(rx_node) in nodes_pos:
                    p1 = nodes_pos[str(tx_node)]
                    p2 = nodes_pos[str(rx_node)]
                    dist = math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                    if dist > max_dist:
                        max_dist = dist

print("Max successful Rx distance:", max_dist)
