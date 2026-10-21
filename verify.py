import joblib
import pickle
import os

dst = r"C:\Users\divya\OneDrive\Desktop\ML_MANET\manet-backend\models\baseline"

models = ["RandomForest.pkl", "XGBoost.pkl", "CatBoost.pkl", "SVM.pkl", "MLP.pkl"]
for m in models:
    try:
        path = os.path.join(dst, m)
        try:
            model = joblib.load(path)
        except:
            with open(path, 'rb') as f:
                model = pickle.load(f)
        
        feat_in = getattr(model, 'n_features_in_', None)
        feat_names = getattr(model, 'feature_names_in_', None)
        print(f"{m}: n_features_in_={feat_in}, feature_names_in_={list(feat_names) if feat_names is not None else None}")
    except Exception as e:
        print(f"{m}: Error {e}")

try:
    scaler_path = os.path.join(dst, "scaler.pkl")
    scaler = joblib.load(scaler_path)
    print(f"scaler.pkl: n_features_in_={scaler.n_features_in_}, feature_names_in_={list(scaler.feature_names_in_) if hasattr(scaler, 'feature_names_in_') else None}")
except Exception as e:
    print(f"scaler.pkl: Error {e}")
