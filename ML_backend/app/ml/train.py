import pandas as pd
import joblib
from pathlib import Path
import json
import datetime
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report
import sys
import logging

from app.ml.preprocessing import DataPreprocessor
from app.ml.feature_selection import RFECVSelector
from app.ml.models import get_models

logger = logging.getLogger(__name__)

class MLPipeline:
    def __init__(self, dataset_path: str, experiment_name: str = "baseline"):
        self.dataset_path = dataset_path
        self.experiment_name = experiment_name
        self.outputs_ml_dir = Path(__file__).parent.parent.parent / "outputs" / "ml" / experiment_name
        self.models_dir = Path(__file__).parent.parent.parent / "models" / experiment_name
        
        self.outputs_ml_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics = {}
        
    def train_and_evaluate(self):
        """
        Executes the strict non-leaking ML training pipeline.
        """
        # 1. Preprocessing
        preprocessor = DataPreprocessor(experiment_name=self.experiment_name)
        df = preprocessor.load_and_clean_data(self.dataset_path)
        
        if df.empty or "label" not in df.columns:
            raise ValueError("Dataset empty or missing label.")
            
        labels = df["label"].value_counts().to_dict()
        
        X_train, X_test, y_train, y_test = preprocessor.prepare_data(df, test_size=0.3, random_state=42)
        preprocessor.save_scaler()
        
        # 2. RFECV (Strictly on Training Data)
        selector = RFECVSelector(random_state=42)
        X_train_selected = selector.fit_transform(X_train, y_train)
        X_test_selected = selector.transform(X_test) # Transform unseen data using fitted selector
        
        # 3. Models
        models = get_models(random_state=42)
        
        for name, model in models.items():
            try:
                # Train
                model.fit(X_train_selected, y_train)
                
                # Predict on UNSEEN test set
                y_pred = model.predict(X_test_selected)
                
                # Calculate metrics
                acc = accuracy_score(y_test, y_pred)
                
                # Malicious class metrics (label=1)
                prec = precision_score(y_test, y_pred, zero_division=0)
                rec = recall_score(y_test, y_pred, zero_division=0)
                f1 = f1_score(y_test, y_pred, zero_division=0)
                
                cm = confusion_matrix(y_test, y_pred, labels=[0,1])
                tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0,0,0,0)
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
                
                report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
                
                self.metrics[name] = {
                    "Accuracy": acc,
                    "Precision": prec,
                    "Recall": rec,
                    "F1": f1,
                    "FPR": fpr,
                    "ConfusionMatrix": {"TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp)},
                    "ClassificationReport": report
                }
                
                # Save Model
                joblib.dump(model, self.models_dir / f"{name}.pkl")
                
            except Exception as e:
                logger.error(f"Failed to train {name}: {e}")
                self.metrics[name] = {"error": str(e)}

        # 4. Save Metadata
        metadata = {
            "dataset_path": str(self.dataset_path),
            "dataset_row_count": len(df),
            "feature_count_total": len(X_train.columns),
            "class_distribution": labels,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "selected_features": selector.selected_features,
            "model_names": list(models.keys()),
            "metrics": self.metrics,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        (self.outputs_ml_dir / "experiment_metadata.json").write_text(json.dumps(metadata, indent=4))
        
        return metadata
