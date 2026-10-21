import re
import os
from collections import defaultdict

_LINE_PAT = re.compile(
    r'^(.)\s+([\d.]+)\s+/NodeList/(\d+)/\$ns3::Ipv4L3Protocol/(Tx|Rx|Drop)\((\d+)\)\s+'
    r'ns3::Ipv4Header\s+\(.*id\s+(\d+)\s+protocol\s+\d+.*length:\s+\d+\s+10\.1\.1\.(\d+)\s+>\s+10\.1\.1\.(\d+)\)'
)

def _parse_events(lines, src_ip, dst_ip):
    events = []
    for line in lines:
        if src_ip not in line or dst_ip not in line:
            continue
        m = _LINE_PAT.match(line)
        if not m:
            continue
        ev_char, ts_s, node_s, txrx, iface_s, pid_s, pkt_src_node, pkt_dst_node = m.groups()
        
        pkt_src = f"10.1.1.{pkt_src_node}"
        pkt_dst = f"10.1.1.{pkt_dst_node}"
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

tr_file = r'C:\Users\divya\OneDrive\Desktop\MANET\manet-backend\simulation\results\dynamic\run_20260911_134835_206375b4_10nodes_attack3_route.tr'
with open(tr_file, 'r') as f:
    lines = f.readlines()

events = _parse_events(lines, "10.1.1.1", "10.1.1.10")

pid_paths = {}
for e in events:
    pid = e['pid']
    if pid not in pid_paths:
        pid_paths[pid] = {'nodes': [], 'reached': False}
        
    if e['txrx'] == 'Tx' and e['iface'] == 1:
        if not pid_paths[pid]['nodes'] or pid_paths[pid]['nodes'][-1] != e['node']:
            pid_paths[pid]['nodes'].append(e['node'])
            
    if e['node'] == 9 and e['txrx'] == 'Rx' and e['iface'] == 1:
        pid_paths[pid]['reached'] = True

path_counts = defaultdict(int)
for pid, info in pid_paths.items():
    if not info['nodes'] or info['nodes'][0] != 0:
        continue
    path = tuple(info['nodes'])
    path_counts[(path, info['reached'])] += 1

print("Paths taken by packets (ordered by frequency):")
for (path, reached), count in sorted(path_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"Count: {count:3d} | Path: {path} | Reached Dest: {reached}")

