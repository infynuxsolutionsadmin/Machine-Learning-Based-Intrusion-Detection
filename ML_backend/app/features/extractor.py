from app.features.physical import extract_physical_features
from app.features.mac import extract_mac_features
from app.features.network import extract_network_features
import pandas as pd
from typing import Dict, Any

class CrossLayerExtractor:
    def __init__(self, flowmon_df: pd.DataFrame, trace_csv_df: pd.DataFrame, route_tr_df: pd.DataFrame):
        self.flowmon_df = flowmon_df
        self.trace_csv_df = trace_csv_df
        self.route_tr_df = route_tr_df

    def extract_all(self) -> pd.DataFrame:
        """
        Combines Physical, MAC, and Network features into a single dataset.
        """
        # Network features form the base since we actually have them
        base_df = extract_network_features(self.flowmon_df, self.trace_csv_df, self.route_tr_df)
        if base_df.empty:
            return base_df
            
        phy_status = extract_physical_features({})
        mac_status = extract_mac_features({})
        
        # Explicitly define missing features for full schema compliance
        for key in phy_status.keys():
            if key not in ["status", "reason"]:
                base_df[f"phy_{key}"] = None
                
        for key in mac_status.keys():
            if key not in ["status", "reason"]:
                base_df[f"mac_{key}"] = None
                
        return base_df
