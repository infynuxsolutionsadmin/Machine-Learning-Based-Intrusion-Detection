import pandas as pd
import joblib
import json
from pathlib import Path
from app.ml.preprocessing import DataPreprocessor

class MLPredictor:
    def __init__(self, model_name: str = "RandomForest", experiment_name: str = "baseline"):
        self.model_name = model_name
        self.experiment_name = experiment_name
        self.models_dir = Path(__file__).parent.parent.parent / "models" / experiment_name
        self.outputs_dir = Path(__file__).parent.parent.parent / "outputs" / "ml" / experiment_name
        
        # Load scaler
        self.preprocessor = DataPreprocessor(experiment_name=self.experiment_name)
        try:
            self.preprocessor.load_scaler()
        except FileNotFoundError:
            raise RuntimeError("ML Pipeline not trained. Scaler missing.")
            
        # Load Selected Features from metadata
        meta_path = self.models_dir / "experiment_metadata.json"
        if not meta_path.exists():
            raise RuntimeError("ML Pipeline not trained. Metadata missing.")
        self.selected_features = json.loads(meta_path.read_text()).get("selected_features", [])
        
        # Load Model
        model_path = self.models_dir / f"{self.model_name}.pkl"
        if not model_path.exists():
            raise RuntimeError(f"Model {self.model_name} not found.")
        self.model = joblib.load(model_path)
        
    def predict(self, df: pd.DataFrame) -> dict:
        """Runs the prediction pipeline on fresh data, applying exact transforms."""
        # 1. Strip unavailable columns exactly like preprocessing
        cols_to_drop = [col for col in df.columns if col.startswith("phy_") or col.startswith("mac_")]
        meta_cols = ["time", "node", "label"]
        cols_to_drop.extend([c for c in meta_cols if c in df.columns])
        
        df_clean = df.drop(columns=cols_to_drop, errors="ignore")
        
        # 2. Scale
        # In a real API, the columns must perfectly match the scaler's feature_names_in_
        if hasattr(self.preprocessor.scaler, "feature_names_in_"):
            expected_cols = list(self.preprocessor.scaler.feature_names_in_)
            missing = [c for c in expected_cols if c not in df_clean.columns]
            if missing:
                raise ValueError(f"Input data is missing columns required by the scaler: {missing}")
            # Align order
            df_clean = df_clean[expected_cols]
            
        scaled_array = self.preprocessor.scaler.transform(df_clean)
        df_scaled = pd.DataFrame(scaled_array, columns=df_clean.columns)
        
        # 3. RFECV Feature Filter
        missing_selected = [c for c in self.selected_features if c not in df_scaled.columns]
        if missing_selected:
            raise ValueError(f"Input data is missing RFECV selected features: {missing_selected}")
        
        df_selected = df_scaled[self.selected_features]
        
        # 4. Predict
        predictions = self.model.predict(df_selected)
        
        probabilities = None
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(df_selected)[:, 1].tolist()
            
        return {
            "model": self.model_name,
            "predictions": predictions.tolist(),
            "probabilities": probabilities,
            "selected_features_used": self.selected_features
        }
