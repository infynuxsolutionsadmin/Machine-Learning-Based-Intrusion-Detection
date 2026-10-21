import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import os
import sys

# Assume run from manet-backend directory
sys.path.append(os.getcwd())

SEQ_LENGTH = 5

class TrustLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers):
        super(TrustLSTM, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc1 = nn.Linear(hidden_size, 16)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(16, 1)
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        out = self.fc1(out)
        out = self.relu(out)
        out = self.fc2(out)
        out = self.sigmoid(out)
        return out

trace_file = r'C:\Users\divya\OneDrive\Desktop\Final year_ppt-2026\Vijay_Batch\MANET\manet-backend\simulation\results\dynamic\run_20260925_115317_213cf35a_10nodes_attack2_3_trace.csv'

df = pd.read_csv(trace_file)
df = df.sort_values(by=['node', 'time'])

df['rx_rate'] = df.groupby(['node'])['rx'].diff().fillna(0)
df['fw_rate'] = df.groupby(['node'])['fw'].diff().fillna(0)
df['drop_rate'] = df.groupby(['node'])['drop'].diff().fillna(0)

df['rx_rate'] = df['rx_rate'].clip(lower=0)
df['fw_rate'] = df['fw_rate'].clip(lower=0)
df['drop_rate'] = df['drop_rate'].clip(lower=0)

df['fw_ratio'] = df['fw_rate'] / (df['rx_rate'] + 1e-5)

features = ['rx_rate', 'fw_rate', 'drop_rate', 'fw_ratio']

model = TrustLSTM(input_size=len(features), hidden_size=32, num_layers=1)
model.load_state_dict(torch.load("lstm_trust_model.pth"))
model.eval()

def analyze_node(node):
    print(f"\n--- Node {node} ---")
    node_df = df[df['node'] == node].copy()
    min_trust = 1.0
    min_seq = None
    min_pred = 0
    min_time = 0
    
    for i in range(len(node_df) - SEQ_LENGTH + 1):
        window = node_df.iloc[i : i+SEQ_LENGTH]
        x_seq = window[features].values
        x_tensor = torch.FloatTensor(x_seq).unsqueeze(0)
        
        with torch.no_grad():
            pred = model(x_tensor).item()
            
        trust_score = 1.0 - pred
        
        if trust_score < min_trust:
            min_trust = trust_score
            min_seq = window
            min_pred = pred
            min_time = window.iloc[-1]['time']
            
    print(f"Minimum Trust Score: {min_trust:.4f} at time {min_time}")
    print(f"Predicted Malicious (pred > 0.5): {min_pred > 0.5}")
    if min_seq is not None:
        print("\nFeatures that caused minimum trust score:")
        print(min_seq[['time'] + features])

analyze_node(0)
analyze_node(1)
analyze_node(2)
analyze_node(3)
analyze_node(4)
