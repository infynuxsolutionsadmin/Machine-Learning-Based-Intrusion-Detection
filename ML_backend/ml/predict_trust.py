import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import joblib
import sys
import os

SEQ_LENGTH = 5

class TrustLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers):
        super(TrustLSTM, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc1 = nn.Linear(hidden_size, 16)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(16, 1)
        # Sigmoid removed from model to match training BCEWithLogitsLoss
        
    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        out = self.fc1(out)
        out = self.relu(out)
        out = self.fc2(out)
        return out

def main():
    if len(sys.argv) < 3:
        print("Usage: python predict_trust.py <trace_file.csv> <output_predictions.csv>")
        sys.exit(1)
        
    trace_file = sys.argv[1]
    out_file = sys.argv[2]
    
    if not os.path.exists(trace_file):
        print(f"File {trace_file} not found.")
        sys.exit(1)
        
    df = pd.read_csv(trace_file)
    df = df.sort_values(by=['node', 'time'])
    
    df['rx_rate'] = df.groupby(['node'])['rx'].diff().fillna(0)
    df['fw_rate'] = df.groupby(['node'])['fw'].diff().fillna(0)
    df['drop_rate'] = df.groupby(['node'])['drop'].diff().fillna(0)
    
    df['rx_rate'] = df['rx_rate'].clip(lower=0)
    df['fw_rate'] = df['fw_rate'].clip(lower=0)
    df['drop_rate'] = df['drop_rate'].clip(lower=0)
    
    # Safe fw_ratio computation to avoid 100000+ explosion
    df['fw_ratio'] = df['fw_rate'] / df['rx_rate'].clip(lower=1.0)
    
    features = ['rx_rate', 'fw_rate', 'drop_rate', 'fw_ratio']
    
    # Load Scaler
    scaler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lstm_scaler.pkl")
    if os.path.exists(scaler_path):
        scaler = joblib.load(scaler_path)
    elif os.path.exists("lstm_scaler.pkl"):
        scaler = joblib.load("lstm_scaler.pkl")
    else:
        print("Scaler file lstm_scaler.pkl not found!")
        sys.exit(1)
    
    model = TrustLSTM(input_size=len(features), hidden_size=32, num_layers=1)
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lstm_trust_model.pth")
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path))
    elif os.path.exists("lstm_trust_model.pth"):
        model.load_state_dict(torch.load("lstm_trust_model.pth"))
    else:
        print("Model file lstm_trust_model.pth not found!")
        sys.exit(1)
        
    model.eval()
    
    predictions_out = []
    
    for node in df['node'].unique():
        node_df = df[df['node'] == node].copy()
        if len(node_df) >= SEQ_LENGTH:
            for i in range(len(node_df) - SEQ_LENGTH + 1):
                window = node_df.iloc[i : i+SEQ_LENGTH]
                x_seq = window[features].values
                
                # Apply scaler
                x_scaled = scaler.transform(x_seq)
                
                x_tensor = torch.FloatTensor(x_scaled).unsqueeze(0)
                
                with torch.no_grad():
                    logits = model(x_tensor)
                    prob = torch.sigmoid(logits).item()
                    
                trust_score = 1.0 - prob
                t = window.iloc[-1]['time']
                
                time_out = t + 0.1
                is_mal = 1 if prob > 0.5 else 0
                predictions_out.append(f"{time_out},{node},{trust_score:.4f},{is_mal}")
                    
    with open(out_file, 'w') as f:
        f.write("time,node,score,is_malicious\n")
        for line in predictions_out:
            f.write(line + "\n")
            
    print(f"Predictions written to {out_file}")

if __name__ == "__main__":
    main()
