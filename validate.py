import sys
import os
import json
import pandas as pd
from pathlib import Path
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

base_dir = r"C:\Users\divya\OneDrive\Desktop\ML_MANET\manet-backend"
sys.path.insert(0, base_dir)

from app.simulation.parser import NS3Parser
from app.features.extractor import CrossLayerExtractor
from app.ml.preprocessing import DataPreprocessor
from app.ml.predict import MLPredictor

run_dir = Path(r"C:\Users\divya\OneDrive\Desktop\ML_MANET\backend\outputs\simulations\run_20260923_120928")

print(f"Dataset path: {run_dir}")
with open(run_dir / 'simulation_metadata.json', 'r') as f:
    meta = json.load(f)
    print(f"Malicious nodes: {meta.get('malicious_nodes')}")

# 4. VALIDATE RAW FEATURE SCHEMA
parser = NS3Parser(run_dir)
flowmon_df = parser.parse_flowmon()
trace_df = parser.parse_trace_csv()
route_df = parser.parse_route_tr()

print(f"Trace rows: {len(trace_df)}")
print(f"Has labels: {'label' in trace_df.columns}")

extractor = CrossLayerExtractor(flowmon_df, trace_df, route_df)
df = extractor.extract_all()

print(f"Extractor output rows: {len(df)}")
print(f"Extractor output cols: {df.columns.tolist()}")
print(f"Nulls: {df.isnull().sum().to_dict()}")

preprocessor = DataPreprocessor(experiment_name='baseline')
preprocessor.load_scaler()

# Replicate prediction cleaning
cols_to_drop = [col for col in df.columns if col.startswith('phy_') or col.startswith('mac_')]
meta_cols = ['time', 'node', 'label']
cols_to_drop.extend([c for c in meta_cols if c in df.columns])
df_clean = df.drop(columns=cols_to_drop, errors='ignore')
print(f"Cleaned columns: {df_clean.columns.tolist()}")

# 5. VALIDATE SCALER
expected_cols = list(preprocessor.scaler.feature_names_in_)
print(f"Scaler expected columns: {expected_cols}")
df_clean = df_clean[expected_cols]
print(f"Dataframe before scaling shape: {df_clean.shape}")

scaled_array = preprocessor.scaler.transform(df_clean)
df_scaled = pd.DataFrame(scaled_array, columns=df_clean.columns)

# 6. VALIDATE FEATURE SELECTION
with open(r"C:\Users\divya\OneDrive\Desktop\ML_MANET\manet-backend\models\baseline\experiment_metadata.json", 'r') as f:
    meta = json.load(f)
    sel = meta['selected_features']
print(f"Selected features: {sel}")
df_selected = df_scaled[sel]
print(f"Model input shape: {df_selected.shape}")

# 7. RUN ALL FIVE MODELS & 8. GROUND TRUTH
models = ['RandomForest', 'XGBoost', 'CatBoost', 'SVM', 'MLP']
for m in models:
    try:
        predictor = MLPredictor(model_name=m, experiment_name='baseline')
        res = predictor.predict(df)
        preds = res['predictions']
        print(f'\nModel: {m}')
        print(f'Prediction count: {len(preds)}')
        print(f'Unique classes: {set(preds)}')
        
        # Ground truth
        if 'label' in df.columns:
            y_true = df['label']
            print(f'Accuracy: {accuracy_score(y_true, preds):.4f}')
            print(f'Precision: {precision_score(y_true, preds, zero_division=0):.4f}')
            print(f'Recall: {recall_score(y_true, preds, zero_division=0):.4f}')
            print(f'F1: {f1_score(y_true, preds, zero_division=0):.4f}')
            print(f'Confusion Matrix: \n{confusion_matrix(y_true, preds)}')
        else:
            print('Evaluation metrics not calculated because ground truth alignment cannot be verified.')
            
    except Exception as e:
        print(f'Model {m} failed: {e}')
