import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class NS3Parser:
    def __init__(self, run_dir: Path, run_id: str = None):
        self.run_dir = run_dir
        self.run_id = run_id
        
    def parse_flowmon(self) -> pd.DataFrame:
        filename = f"run_{self.run_id}.xml" if self.run_id else "flowmon.xml"
        flowmon_file = self.run_dir / filename
        if not flowmon_file.exists() or flowmon_file.stat().st_size == 0:
            logger.warning(f"FlowMonitor file missing or empty: {flowmon_file}")
            return pd.DataFrame()
            
        try:
            tree = ET.parse(flowmon_file)
            root = tree.getroot()
            
            flows_data = []
            for flow in root.findall(".//FlowStats/Flow"):
                flow_id = flow.get("flowId")
                rx_packets = float(flow.get("rxPackets", 0))
                tx_packets = float(flow.get("txPackets", 0))
                delay_sum = flow.get("delaySum") # formatted like "+6021671954.0ns"
                
                # Strip ns and +, parse delay
                delay_ns = 0.0
                if delay_sum and delay_sum.endswith("ns"):
                    delay_ns = float(delay_sum.replace("+", "").replace("ns", ""))
                
                delay_s = delay_ns / 1e9
                pdr = (rx_packets / tx_packets) if tx_packets > 0 else 0.0
                avg_delay = (delay_s / rx_packets) if rx_packets > 0 else 0.0
                
                flows_data.append({
                    "flow_id": flow_id,
                    "tx_packets": tx_packets,
                    "rx_packets": rx_packets,
                    "pdr": pdr,
                    "avg_delay_s": avg_delay
                })
            
            return pd.DataFrame(flows_data)
        except Exception as e:
            logger.error(f"Error parsing FlowMonitor XML: {e}")
            return pd.DataFrame()

    def parse_trace_csv(self) -> pd.DataFrame:
        filename = f"run_{self.run_id}_trace.csv" if self.run_id else "trace.csv"
        trace_file = self.run_dir / filename
        if not trace_file.exists() or trace_file.stat().st_size == 0:
            logger.warning(f"Trace CSV missing or empty: {trace_file}")
            return pd.DataFrame()
        
        try:
            df = pd.read_csv(trace_file)
            return df
        except Exception as e:
            logger.error(f"Error parsing trace.csv: {e}")
            return pd.DataFrame()
            
    def parse_route_tr(self) -> pd.DataFrame:
        filename = f"run_{self.run_id}_route.tr" if self.run_id else "route.tr"
        route_file = self.run_dir / filename
        if not route_file.exists() or route_file.stat().st_size == 0:
            logger.warning(f"Route trace missing or empty: {route_file}")
            return pd.DataFrame()
            
        try:
            # Route trace parsing is complex. We will count AODV control messages per node.
            # Typical line: t 2.000000000 /NodeList/0/DeviceList/1/... 
            control_msg_counts = {}
            with open(route_file, 'r') as f:
                for line in f:
                    if "AODV" in line or "aodv" in line:
                        # Extract node id roughly
                        # Assuming format /NodeList/<node_id>/...
                        parts = line.split("/NodeList/")
                        if len(parts) > 1:
                            node_id = parts[1].split("/")[0]
                            control_msg_counts[node_id] = control_msg_counts.get(node_id, 0) + 1
                            
            df = pd.DataFrame(list(control_msg_counts.items()), columns=["node_id", "aodv_control_msgs"])
            return df
        except Exception as e:
            logger.error(f"Error parsing route trace: {e}")
            return pd.DataFrame()

    def parse_energy_csv(self) -> pd.DataFrame:
        energy_file = self.run_dir / "energy.csv"
        if not energy_file.exists() or energy_file.stat().st_size == 0:
            return pd.DataFrame()
            
        try:
            df = pd.read_csv(energy_file)
            return df
        except Exception as e:
            logger.error(f"Error parsing energy.csv: {e}")
            return pd.DataFrame()
