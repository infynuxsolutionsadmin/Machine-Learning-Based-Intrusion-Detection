from typing import Dict, Any
import pandas as pd

def extract_network_features(flowmon_df: pd.DataFrame, trace_csv_df: pd.DataFrame, route_tr_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts network layer features using real FlowMonitor, route trace, and custom CSV outputs.
    Combines these into a node-level feature representation.
    """
    # If no data, return empty
    if trace_csv_df.empty:
        return pd.DataFrame()
        
    # Start with trace CSV as the base (contains time, node, rx, fw, drop, label)
    # trace.csv schema: time,node,rx,fw,drop,label
    df = trace_csv_df.copy()
    
    # Calculate drops ratio based on rx
    df["drop_ratio"] = df.apply(lambda row: row["drop"] / row["rx"] if row["rx"] > 0 else 0.0, axis=1)
    
    # Merge Control Message Frequency from route trace
    df["control_message_frequency"] = 0.0
    if not route_tr_df.empty:
        # route_tr_df schema: node_id, aodv_control_msgs
        route_tr_df["node_id"] = route_tr_df["node_id"].astype(str)
        df["node"] = df["node"].astype(str)
        
        # Merge on node
        df = df.merge(route_tr_df, left_on="node", right_on="node_id", how="left")
        df["control_message_frequency"] = df["aodv_control_msgs"].fillna(0.0)
        df.drop(columns=["node_id", "aodv_control_msgs"], inplace=True, errors="ignore")
    
    # FlowMonitor provides per-flow data (End to end delay, PDR). 
    # Since flows are between specific source/dest nodes and trace.csv is per-node, 
    # we can aggregate average PDR and Delay from FlowMonitor to append as general network condition,
    # or if we had flow->node mapping, append it accurately. 
    # For now, we will compute global network averages from flowmon to augment the dataset,
    # or just keep it node-specific.
    if not flowmon_df.empty:
        avg_network_pdr = flowmon_df["pdr"].mean()
        avg_network_delay = flowmon_df["avg_delay_s"].mean()
        df["network_avg_pdr"] = avg_network_pdr
        df["network_avg_delay"] = avg_network_delay
    else:
        df["network_avg_pdr"] = 0.0
        df["network_avg_delay"] = 0.0

    return df
