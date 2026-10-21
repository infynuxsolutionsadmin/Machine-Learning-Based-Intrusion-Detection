import xml.etree.ElementTree as ET
import csv
import sys
import os

def parse_flowmon(xml_file, csv_file):
    if not os.path.exists(xml_file):
        print(f"File {xml_file} not found.")
        sys.exit(1)
        
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # We want to extract Flow metrics
    with open(csv_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['flow_id', 'source_addr', 'dest_addr', 'tx_packets', 'rx_packets', 'lost_packets', 'pdr_percent', 'throughput_kbps', 'mean_delay_ms'])

        flow_stats = {}
        for flow in root.findall('.//FlowStats/Flow'):
            flow_id = flow.get('flowId')
            flow_stats[flow_id] = {
                'tx_packets': int(flow.get('txPackets', 0)),
                'rx_packets': int(flow.get('rxPackets', 0)),
                'lost_packets': int(flow.get('lostPackets', 0)),
                'rx_bytes': int(flow.get('rxBytes', 0)),
                'delay_sum': flow.get('delaySum', '0ns')
            }

        for flow in root.findall('.//Ipv4FlowClassifier/Flow'):
            flow_id = flow.get('flowId')
            if flow_id not in flow_stats:
                continue
                
            source = flow.get('sourceAddress')
            dest = flow.get('destinationAddress')
            
            tx_packets = flow_stats[flow_id]['tx_packets']
            rx_packets = flow_stats[flow_id]['rx_packets']
            lost_packets = flow_stats[flow_id]['lost_packets']
            rx_bytes = flow_stats[flow_id]['rx_bytes']
            delay_sum = flow_stats[flow_id]['delay_sum']
            
            pdr = (rx_packets / tx_packets * 100) if tx_packets > 0 else 0
            
            # Simple approximation for duration (assuming 60s sim)
            duration = 60.0 
            throughput = (rx_bytes * 8) / duration / 1000 # kbps

            # Parse delay (removing '+' and 'ns')
            try:
                delay_ns = float(delay_sum.replace('+', '').replace('ns', ''))
                mean_delay_ms = (delay_ns / 1000000) / rx_packets if rx_packets > 0 else 0
            except:
                mean_delay_ms = 0

            writer.writerow([flow_id, source, dest, tx_packets, rx_packets, lost_packets, round(pdr, 2), round(throughput, 2), round(mean_delay_ms, 2)])
            print(f"Flow {flow_id}: PDR={round(pdr, 2)}% | Throughput={round(throughput, 2)} kbps | Delay={round(mean_delay_ms, 2)} ms")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        input_xml = sys.argv[1]
        output_csv = sys.argv[2]
    else:
        input_xml = "manet-flowmon-results.xml"
        output_csv = "/mnt/c/Users/divya/OneDrive/Desktop/MANET/manet-backend/simulation/results/results.csv"
        
    parse_flowmon(input_xml, output_csv)
