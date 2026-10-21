import pandas as pd
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DataPreprocessor:
    def __init__(self, experiment_name: str = "baseline"):
        self.scaler = StandardScaler()
        self.feature_columns = None
        self.experiment_name = experiment_name
        self.models_dir = Path(__file__).parent.parent.parent / "models" / experiment_name
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
    def load_and_clean_data(self, dataset_path: str) -> pd.DataFrame:
        """Loads dataset and drops physically unavailable columns from Phase 2."""
        df = pd.read_csv(dataset_path)
        
        # Drop columns marked as unavailable in Phase 2
        cols_to_drop = [col for col in df.columns if col.startswith("phy_") or col.startswith("mac_")]
        
        # Drop non-feature meta-columns, but KEEP simulation_id for grouped splitting
        meta_cols = ["time", "node", "is_attack_sim"]
        
        df = df.drop(columns=cols_to_drop, errors="ignore")
        return df

    def prepare_data(self, df: pd.DataFrame, test_size: float = 0.3, random_state: int = 42):
        """
        Separates features/labels, performs stratified split, and fits scaler ONLY on training data.
        """
        if "label" not in df.columns:
            raise ValueError("Dataset does not contain a 'label' column.")
            
        y = df["label"]
        X = df.drop(columns=["label"])
        # Check if we have simulation_id for grouped split
        if "simulation_id" in df.columns:
            groups = df["simulation_id"]
            X = X.drop(columns=["simulation_id"])
            
        # Drop meta columns from features
        meta_cols = ["time", "node", "is_attack_sim"]
        X = X.drop(columns=[c for c in meta_cols if c in X.columns], errors="ignore")
        
        if "simulation_id" in df.columns:
            self.feature_columns = X.columns.tolist()
            
            gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
            train_idx, test_idx = next(gss.split(X, y, groups))
            
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        else:
            self.feature_columns = X.columns.tolist()
            # Fallback if class is too small for standard stratification
            stratify = y if len(y.unique()) > 1 and y.value_counts().min() > 1 else None
            
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state, stratify=stratify
            )
        
        # Fit scaler ONLY on training data to prevent data leakage
        X_train_scaled = pd.DataFrame(self.scaler.fit_transform(X_train), columns=self.feature_columns, index=X_train.index)
        X_test_scaled = pd.DataFrame(self.scaler.transform(X_test), columns=self.feature_columns, index=X_test.index)
        
        return X_train_scaled, X_test_scaled, y_train, y_test

    def save_scaler(self, filename: str = "scaler.pkl"):
        """Saves the fitted scaler for prediction use."""
        joblib.dump(self.scaler, self.models_dir / filename)
        
    def load_scaler(self, filename: str = "scaler.pkl"):
        """Loads a fitted scaler."""
        scaler_path = self.models_dir / filename
        if not scaler_path.exists():
            raise FileNotFoundError("Scaler artifact not found.")
        self.scaler = joblib.load(scaler_path)
