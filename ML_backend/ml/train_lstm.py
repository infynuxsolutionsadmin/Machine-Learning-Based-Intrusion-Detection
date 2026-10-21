import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
import joblib
import json
import os

SEQ_LENGTH = 5

def create_sequences(data, labels, seq_length):
    sequences = []
    seq_labels = []
    
    for i in range(len(data) - seq_length + 1):
        seq = data[i:i+seq_length]
        label = labels[i+seq_length-1]
        sequences.append(seq)
        seq_labels.append(label)
        
    return np.array(sequences), np.array(seq_labels)

class TrustLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers):
        super(TrustLSTM, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc1 = nn.Linear(hidden_size, 16)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(16, 1)
        # No Sigmoid here, we use BCEWithLogitsLoss
        
    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        out = self.fc1(out)
        out = self.relu(out)
        out = self.fc2(out)
        return out

def main():
    print("Loading dataset...")
    if not os.path.exists("trust_dataset.csv"):
        print("Dataset not found!")
        return

    df = pd.read_csv("trust_dataset.csv")
    df = df.sort_values(by=['run_id', 'node', 'time'])
    
    df['rx_rate'] = df.groupby(['run_id', 'node'])['rx'].diff().fillna(0)
    df['fw_rate'] = df.groupby(['run_id', 'node'])['fw'].diff().fillna(0)
    df['drop_rate'] = df.groupby(['run_id', 'node'])['drop'].diff().fillna(0)
    
    df['rx_rate'] = df['rx_rate'].clip(lower=0)
    df['fw_rate'] = df['fw_rate'].clip(lower=0)
    df['drop_rate'] = df['drop_rate'].clip(lower=0)
    
    # Safe fw_ratio computation to avoid 100000+ explosion
    df['fw_ratio'] = df['fw_rate'] / df['rx_rate'].clip(lower=1.0)
    
    features = ['rx_rate', 'fw_rate', 'drop_rate', 'fw_ratio']
    
    X_list = []
    y_list = []
    
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
                X_list.extend(X_seq)
                y_list.extend(y_seq)
                
    X = np.array(X_list)
    y = np.array(y_list)
    
    # Preprocessing
    scaler = StandardScaler()
    samples, seq, feats = X.shape
    X_reshaped = X.reshape(-1, feats)
    X_scaled = scaler.fit_transform(X_reshaped)
    X = X_scaled.reshape(samples, seq, feats)
    
    joblib.dump(scaler, "lstm_scaler.pkl")
    print("Saved lstm_scaler.pkl")
    
    split_idx = int(0.8 * len(X))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    num_pos = np.sum(y_train == 1)
    num_neg = np.sum(y_train == 0)
    pos_weight_val = num_neg / max(num_pos, 1.0)
    print(f"Training Class balance: Normal={num_neg}, Malicious={num_pos}, Calculated pos_weight={pos_weight_val:.2f}")
    
    train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train).unsqueeze(1))
    test_dataset = TensorDataset(torch.FloatTensor(X_test), torch.FloatTensor(y_test).unsqueeze(1))
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
    
    model = TrustLSTM(input_size=len(features), hidden_size=32, num_layers=1)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight_val]))
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    
    best_f1 = -1.0
    
    for epoch in range(20):
        model.train()
        total_loss = 0
        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        # Eval
        model.eval()
        all_preds = []
        all_labels = []
        with torch.no_grad():
            for batch_X, batch_y in test_loader:
                outputs = model(batch_X)
                probs = torch.sigmoid(outputs)
                predicted = (probs > 0.5).float()
                all_preds.extend(predicted.numpy())
                all_labels.extend(batch_y.numpy())
                
        all_preds = np.array(all_preds).flatten()
        all_labels = np.array(all_labels).flatten()
        
        acc = (all_preds == all_labels).mean()
        precision = precision_score(all_labels, all_preds, zero_division=0)
        recall = recall_score(all_labels, all_preds, zero_division=0)
        f1 = f1_score(all_labels, all_preds, zero_division=0)
        
        print(f"Epoch {epoch+1}/20, Loss: {total_loss/len(train_loader):.4f}, F1: {f1:.4f}")
        
        if f1 > best_f1:
            best_f1 = f1
            torch.save(model.state_dict(), "lstm_trust_model.pth")
            print("  -> Saved new best model!")
    
    # Load best model for final testing
    model.load_state_dict(torch.load("lstm_trust_model.pth"))
    model.eval()
    all_preds = []
    all_labels = []
    test_loss = 0
    with torch.no_grad():
        for batch_X, batch_y in test_loader:
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            test_loss += loss.item()
            probs = torch.sigmoid(outputs)
            predicted = (probs > 0.5).float()
            all_preds.extend(predicted.numpy())
            all_labels.extend(batch_y.numpy())
            
    all_preds = np.array(all_preds).flatten()
    all_labels = np.array(all_labels).flatten()
    
    acc = (all_preds == all_labels).mean()
    precision = precision_score(all_labels, all_preds, zero_division=0)
    recall = recall_score(all_labels, all_preds, zero_division=0)
    f1 = f1_score(all_labels, all_preds, zero_division=0)
    cm = confusion_matrix(all_labels, all_preds)
    
    print("\nFinal Test Metrics:")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    print("Confusion Matrix:")
    print(cm)
    
    with open("lstm_metrics.json", "w") as f:
        json.dump({
            "test_accuracy": float(acc), 
            "test_loss": test_loss/len(test_loader), 
            "samples": len(test_dataset),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "confusion_matrix": cm.tolist()
        }, f)

if __name__ == "__main__":
    main()
