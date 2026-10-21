import pandas as pd
import json

def analyze_dataset():
    df = pd.read_csv("trust_dataset.csv")
    
    print("=== DATASET OVERVIEW ===")
    print(f"Total rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    
    if 'label' in df.columns:
        counts = df['label'].value_counts()
        print("\n=== CLASS BALANCE ===")
        print(counts)
        if 0 in counts and 1 in counts:
            print(f"Normal (0): {counts[0]} ({(counts[0]/len(df))*100:.2f}%)")
            print(f"Malicious (1): {counts[1]} ({(counts[1]/len(df))*100:.2f}%)")
    
    print("\n=== RUN ID & NODES ===")
    if 'run_id' in df.columns:
        print(f"Number of unique runs: {df['run_id'].nunique()}")
    if 'node' in df.columns:
        print(f"Nodes per run: {df.groupby('run_id')['node'].nunique().mean():.1f} avg")
        
    print("\n=== FEATURE ENGINEERING ===")
    df = df.sort_values(by=['run_id', 'node', 'time'])
    df['rx_rate'] = df.groupby(['run_id', 'node'])['rx'].diff().fillna(0).clip(lower=0)
    df['fw_rate'] = df.groupby(['run_id', 'node'])['fw'].diff().fillna(0).clip(lower=0)
    df['drop_rate'] = df.groupby(['run_id', 'node'])['drop'].diff().fillna(0).clip(lower=0)
    
    # Safe fw_ratio computation to avoid 100000+ explosion
    df['fw_ratio'] = df['fw_rate'] / df['rx_rate'].clip(lower=1.0)
    
    features = ['rx_rate', 'fw_rate', 'drop_rate', 'fw_ratio']
    
    print("\n=== FEATURE STATS (Training Dataset) ===")
    for f in features:
        print(f"{f}: min={df[f].min():.4f}, max={df[f].max():.4f}, mean={df[f].mean():.4f}")
        
    print("\n=== MALICIOUS VS NORMAL STATS ===")
    if 'label' in df.columns:
        print("Mean values for Normal (0):")
        print(df[df['label']==0][features].mean())
        print("\nMean values for Malicious (1):")
        print(df[df['label']==1][features].mean())
        

if __name__ == "__main__":
    analyze_dataset()
