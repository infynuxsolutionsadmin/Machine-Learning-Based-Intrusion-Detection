import os
import json
import copy
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import TrustLSTM from ml.train_lstm or redefine it here since we need exact architecture
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

def create_sequences(data, labels, seq_length):
    xs, ys = [], []
    for i in range(len(data) - seq_length + 1):
        x = data[i:(i + seq_length)]
        y = labels[i + seq_length - 1]
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)

def process_dataset(dataset_path, run_id_val="current_run"):
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")

    df = pd.read_csv(dataset_path)
    
    if 'run_id' not in df.columns:
        df['run_id'] = run_id_val
        
    df = df.sort_values(by=['run_id', 'node', 'time'])
    
    df['rx_rate'] = df.groupby(['run_id', 'node'])['rx'].diff().fillna(0).clip(lower=0)
    df['fw_rate'] = df.groupby(['run_id', 'node'])['fw'].diff().fillna(0).clip(lower=0)
    df['drop_rate'] = df.groupby(['run_id', 'node'])['drop'].diff().fillna(0).clip(lower=0)
    df['fw_ratio'] = df['fw_rate'] / (df['rx_rate'] + 1e-5)
    
    features = ['rx_rate', 'fw_rate', 'drop_rate', 'fw_ratio']
    
    SEQ_LENGTH = 5
    X_list, y_list, node_list = [], [] , []
    
    for run_id in df['run_id'].unique():
        run_df = df[df['run_id'] == run_id]
        for node in run_df['node'].unique():
            node_df = run_df[run_df['node'] == node]
            if len(node_df) >= SEQ_LENGTH:
                X_seq, y_seq = create_sequences(
                    node_df[features].values,
                    node_df['label'].values,
                    SEQ_LENGTH
                )
                X_list.append(X_seq)
                y_list.append(y_seq)
                node_list.extend([node] * len(y_seq))
                
    X = np.vstack(X_list)
    y = np.concatenate(y_list)
    nodes = np.array(node_list)
    
    return X, y, nodes, len(features)

def train_client(global_model_state, X_local, y_local, epochs, lr, input_size):
    # Initialize local model with global parameters
    local_model = TrustLSTM(input_size=input_size, hidden_size=32, num_layers=1)
    local_model.load_state_dict(global_model_state)
    local_model.train()
    
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(local_model.parameters(), lr=lr)
    
    X_t = torch.FloatTensor(X_local)
    y_t = torch.FloatTensor(y_local).view(-1, 1)
    
    train_data = TensorDataset(X_t, y_t)
    train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
    
    total_loss = 0.0
    for epoch in range(epochs):
        epoch_loss = 0.0
        for inputs, targets in train_loader:
            optimizer.zero_grad()
            outputs = local_model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
        total_loss += epoch_loss / max(1, len(train_loader))
        
    avg_loss = total_loss / epochs
    
    # Calculate local accuracy
    local_model.eval()
    with torch.no_grad():
        preds = local_model(X_t)
        predicted_classes = (preds > 0.5).float()
        accuracy = (predicted_classes == y_t).sum().item() / len(y_t)
        
    return local_model.state_dict(), avg_loss, accuracy

def evaluate_model(model_state, X_eval, y_eval, input_size):
    model = TrustLSTM(input_size=input_size, hidden_size=32, num_layers=1)
    model.load_state_dict(model_state)
    model.eval()
    
    criterion = nn.BCELoss()
    X_t = torch.FloatTensor(X_eval)
    y_t = torch.FloatTensor(y_eval).view(-1, 1)
    
    with torch.no_grad():
        preds = model(X_t)
        loss = criterion(preds, y_t).item()
        predicted_classes = (preds > 0.5).float()
        accuracy = (predicted_classes == y_t).sum().item() / len(y_t)
        
    return loss, accuracy

def fed_avg(client_updates):
    # client_updates is a list of tuples: (state_dict, sample_count)
    total_samples = sum(count for _, count in client_updates)
    
    global_dict = copy.deepcopy(client_updates[0][0])
    for k in global_dict.keys():
        global_dict[k] = torch.zeros_like(global_dict[k])
        for client_dict, sample_count in client_updates:
            weight = sample_count / total_samples
            global_dict[k] += client_dict[k] * weight
            
    return global_dict

def run_federated_learning(trace_csv_path, fl_output_dir, num_clients=3, num_rounds=5, run_id="dynamic_run"):
    NUM_CLIENTS = num_clients
    NUM_ROUNDS = num_rounds
    LOCAL_EPOCHS = 3
    LEARNING_RATE = 0.01
    
    print(f"[FL] Starting Simulated Federated Learning for run: {run_id}")
    X, y, nodes, input_size = process_dataset(trace_csv_path, run_id)
    
    metrics = {
        "status": "completed",
        "num_clients": NUM_CLIENTS,
        "num_rounds": NUM_ROUNDS,
        "rounds": []
    }
    
    if len(X) == 0:
        print("[FL] Insufficient samples in the trace to run Federated Learning.")
        metrics["status"] = "failed"
        metrics["reason"] = "Insufficient samples to form sequences."
        os.makedirs(fl_output_dir, exist_ok=True)
        with open(os.path.join(fl_output_dir, "fl_metrics.json"), "w") as f:
            json.dump(metrics, f, indent=4)
        return metrics
    
    # Create deterministic holdout set for global evaluation
    X_train, X_eval, y_train, y_eval, nodes_train, _ = train_test_split(
        X, y, nodes, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"[FL] Total global training samples: {len(X_train)}")
    print(f"[FL] Total holdout evaluation samples: {len(X_eval)}")
    
    # Initialize global model
    global_model = TrustLSTM(input_size=input_size, hidden_size=32, num_layers=1)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_model_path = os.path.join(BASE_DIR, "lstm_trust_model.pth")
    if os.path.exists(base_model_path):
        print(f"[FL] Initializing global model from {base_model_path}")
        global_model.load_state_dict(torch.load(base_model_path))
    else:
        print("[FL] Initializing global model from scratch")
        
    global_state = global_model.state_dict()
    
    for round_num in range(1, NUM_ROUNDS + 1):
        print(f"\n[FL] --- Round {round_num}/{NUM_ROUNDS} ---")
        client_updates = []
        round_client_metrics = []
        
        # Simulated Clients
        for client_id in range(NUM_CLIENTS):
            # Deterministic partition: nodes % NUM_CLIENTS == client_id
            client_mask = (nodes_train % NUM_CLIENTS) == client_id
            X_local = X_train[client_mask]
            y_local = y_train[client_mask]
            sample_count = len(X_local)
            
            if sample_count == 0:
                print(f"[FL] Client {client_id} has no data. Skipping.")
                continue
                
            print(f"[FL] Client {client_id} local training on {sample_count} samples...")
            # Local training happens securely here
            local_state, local_loss, local_acc = train_client(
                global_state, X_local, y_local, LOCAL_EPOCHS, LEARNING_RATE, input_size
            )
            print(f"[FL] Client {client_id} sending model parameters only")
            print(f"[FL] Raw client data remains local")
            
            client_updates.append((local_state, sample_count))
            round_client_metrics.append({
                "client_id": client_id,
                "samples": sample_count,
                "local_loss": local_loss,
                "local_accuracy": local_acc
            })
            
        # Server Aggregation (FedAvg)
        if not client_updates:
            print("[FL] No client updates received. Aborting.")
            break
            
        print(f"[FL] Server received updates from {len(client_updates)} clients. Performing FedAvg...")
        global_state = fed_avg(client_updates)
        
        # Global Evaluation
        global_loss, global_acc = evaluate_model(global_state, X_eval, y_eval, input_size)
        print(f"[FL] Round {round_num} Global Evaluation - Loss: {global_loss:.4f}, Accuracy: {global_acc*100:.2f}%")
        
        metrics["rounds"].append({
            "round": round_num,
            "global_loss": global_loss,
            "global_accuracy": global_acc,
            "clients": round_client_metrics
        })
        
    # Save Artifacts
    os.makedirs(fl_output_dir, exist_ok=True)
    model_save_path = os.path.join(fl_output_dir, "federated_global_model.pth")
    metrics_save_path = os.path.join(fl_output_dir, "fl_metrics.json")
    
    torch.save(global_state, model_save_path)
    with open(metrics_save_path, "w") as f:
        json.dump(metrics, f, indent=4)
        
    print(f"\n[FL] Federated Learning Complete!")
    print(f"[FL] Global model saved to {model_save_path}")
    print(f"[FL] Metrics saved to {metrics_save_path}")
    
    return metrics

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace_csv", type=str, required=True, help="Path to the dynamic trace CSV")
    parser.add_argument("--out_dir", type=str, required=True, help="Directory to save FL artifacts")
    parser.add_argument("--clients", type=int, default=3, help="Number of FL clients")
    parser.add_argument("--rounds", type=int, default=5, help="Number of FL rounds")
    parser.add_argument("--run_id", type=str, required=True, help="The current simulation run ID")
    args = parser.parse_args()
    
    run_federated_learning(
        trace_csv_path=args.trace_csv,
        fl_output_dir=args.out_dir,
        num_clients=args.clients,
        num_rounds=args.rounds,
        run_id=args.run_id
    )
