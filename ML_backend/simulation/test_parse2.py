import re
import sys
import json

def test_parse(tr_file, nNodes):
    src_ip = "10.1.1.1"
    dst_ip = f"10.1.1.{nNodes}"
    src_node = 0
    dst_node = nNodes - 1
    
    with open(tr_file, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        
    # Find first packet transmitted by source
    packet_id = None
    src_tx_regex = re.compile(rf"^t\s+([\d.]+)\s+/NodeList/{src_node}/.*?Tx.*?id (\d+) protocol 17.*?{src_ip} > {dst_ip}")
    for line in lines:
        m = src_tx_regex.search(line)
        if m:
            packet_id = m.group(2)
            break
            
    if not packet_id:
        print("No packets transmitted by source.")
        return
        
    print(f"Tracing packet id: {packet_id}")
    
    # Trace this packet
    tx_regex = re.compile(rf"^t\s+([\d.]+)\s+/NodeList/(\d+)/.*?Tx.*?id {packet_id} protocol 17.*?{src_ip} > {dst_ip}")
    rx_regex = re.compile(rf"^r\s+([\d.]+)\s+/NodeList/(\d+)/.*?Rx.*?id {packet_id} protocol 17.*?{src_ip} > {dst_ip}")
    
    events = []
    for line in lines:
        m_tx = tx_regex.search(line)
        if m_tx:
            t, nid = float(m_tx.group(1)), int(m_tx.group(2))
            events.append((t, nid, 'Tx'))
            continue
            
        m_rx = rx_regex.search(line)
        if m_rx:
            t, nid = float(m_rx.group(1)), int(m_rx.group(2))
            if nid == dst_node:
                events.append((t, nid, 'Rx'))
                
    events.sort(key=lambda x: x[0])
    
    path = []
    for t, nid, evt in events:
        if not path or path[-1] != nid:
            path.append(nid)
            
    print(f"Path: {path}")

if __name__ == '__main__':
    test_parse(sys.argv[1], int(sys.argv[2]))
