import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import joblib
import os

SEQ_LENGTH = 5

class TrustLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers):
        super(TrustLSTM, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc1 = nn.Linear(hidden_size, 16)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(16, 1)
        
    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        out = self.fc1(out)
        out = self.relu(out)
        out = self.fc2(out)
        return out

def analyze_node(df, node_id, scaler, model, features):
    print(f"\n{'='*50}\nANALYZING NODE {node_id}\n{'='*50}")
    node_df = df[df['node'] == node_id].copy()
    if len(node_df) < SEQ_LENGTH:
        print("Not enough sequences")
        return
        
    max_prob = -1.0
    worst_window = None
    worst_x_seq = None
    worst_x_scaled = None
    worst_logit = 0
    
    for i in range(len(node_df) - SEQ_LENGTH + 1):
        window = node_df.iloc[i : i+SEQ_LENGTH]
        x_seq = window[features].values
        
        x_scaled = scaler.transform(x_seq)
        x_tensor = torch.FloatTensor(x_scaled).unsqueeze(0)
        
        with torch.no_grad():
            logits = model(x_tensor)
            prob = torch.sigmoid(logits).item()
            
        if prob > max_prob:
            max_prob = prob
            worst_window = window
            worst_x_seq = x_seq
            worst_x_scaled = x_scaled
            worst_logit = logits.item()
            
    print("1-4. RAW FEATURES (rx_rate, fw_rate, drop_rate, fw_ratio):")
    for t, row in enumerate(worst_x_seq):
        print(f"   t={t}: {row}")
    
    print("\n5. SCALED FEATURES:")
    for t, row in enumerate(worst_x_scaled):
        print(f"   t={t}: {row}")
    
    print(f"\n6. LSTM INPUT TENSOR SHAPE: (1, 5, 4)")
    
    print(f"\n7. RAW MODEL LOGIT: {worst_logit:.4f}")
    print(f"8. SIGMOID MALICIOUS PROB: {max_prob:.4f}")
    print(f"9. FINAL TRUST SCORE: {1.0 - max_prob:.4f}")
    print(f"10. PREDICTED MALICIOUS: {max_prob > 0.5}")
    
    # Check training data similarity
    try:
        train_df = pd.read_csv("trust_dataset.csv")
        train_df['rx_rate'] = train_df.groupby(['run_id', 'node'])['rx'].diff().fillna(0).clip(lower=0)
        train_df['fw_rate'] = train_df.groupby(['run_id', 'node'])['fw'].diff().fillna(0).clip(lower=0)
        train_df['drop_rate'] = train_df.groupby(['run_id', 'node'])['drop'].diff().fillna(0).clip(lower=0)
        train_df['fw_ratio'] = train_df['fw_rate'] / train_df['rx_rate'].clip(lower=1.0)
        
        # Check mean values of Normal vs Malicious in dataset
        mean_norm = train_df[train_df['label']==0][features].mean().values
        mean_mal = train_df[train_df['label']==1][features].mean().values
        
        # Compare the worst feature vector
        last_f = worst_x_seq[-1]
        dist_norm = np.linalg.norm(last_f - mean_norm)
        dist_mal = np.linalg.norm(last_f - mean_mal)
        
        print("\nDATASET SIMILARITY ANALYSIS:")
        print(f"   Worst window last feature: {last_f}")
        print(f"   Mean Normal training sample: {mean_norm}")
        print(f"   Mean Malicious training sample: {mean_mal}")
        print(f"   Euclidean distance to Normal: {dist_norm:.4f}")
        print(f"   Euclidean distance to Malicious: {dist_mal:.4f}")
        if dist_norm < dist_mal:
            print(f"   => Node {node_id} is statistically closer to NORMAL samples.")
        else:
            print(f"   => Node {node_id} is statistically closer to MALICIOUS samples.")
    except Exception as e:
        print("Could not do dataset similarity:", e)


def main():
    trace_file = r"C:\Users\divya\OneDrive\Desktop\Final year_ppt-2026\Vijay_Batch\MANET\manet-backend\simulation\results\dynamic\run_20260925_132209_a820794e_10nodes_attack2_3_trace.csv"
    
    df = pd.read_csv(trace_file)
    df = df.sort_values(by=['node', 'time'])
    
    df['rx_rate'] = df.groupby(['node'])['rx'].diff().fillna(0).clip(lower=0)
    df['fw_rate'] = df.groupby(['node'])['fw'].diff().fillna(0).clip(lower=0)
    df['drop_rate'] = df.groupby(['node'])['drop'].diff().fillna(0).clip(lower=0)
    df['fw_ratio'] = df['fw_rate'] / df['rx_rate'].clip(lower=1.0)
    
    features = ['rx_rate', 'fw_rate', 'drop_rate', 'fw_ratio']
    
    scaler = joblib.load("lstm_scaler.pkl")
    model = TrustLSTM(input_size=len(features), hidden_size=32, num_layers=1)
    model.load_state_dict(torch.load("lstm_trust_model.pth"))
    model.eval()
    
    # Analyze known malicious
    analyze_node(df, 3, scaler, model, features)
    analyze_node(df, 2, scaler, model, features)
    # Analyze normal nodes
    analyze_node(df, 0, scaler, model, features)
    analyze_node(df, 1, scaler, model, features)

if __name__ == "__main__":
    main()
