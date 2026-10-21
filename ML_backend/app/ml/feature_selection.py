from sklearn.feature_selection import RFECV
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
import pandas as pd
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class RFECVSelector:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.selected_features = []
        self.outputs_dir = Path(__file__).parent.parent.parent / "outputs" / "ml"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        
    def fit_transform(self, X_train: pd.DataFrame, y_train: pd.Series) -> pd.DataFrame:
        """
        Runs RFECV on the training data ONLY.
        Uses F1 (weighted) due to heavy class imbalance.
        """
        # Because we have only 3-4 malicious samples in train, standard 5-fold CV will fail
        # if a fold has 0 malicious samples. We use a 3-fold split (since there are ~3 malicious samples).
        n_splits = min(3, y_train.value_counts().min())
        if n_splits < 2:
            # Fallback if too few samples
            logger.warning("Too few samples for StratifiedKFold. Disabling CV for feature selection.")
            cv_strategy = 2 # Just arbitrary minimal value, but might fail stratify
        else:
            cv_strategy = StratifiedKFold(n_splits=n_splits)

        estimator = RandomForestClassifier(random_state=self.random_state, class_weight="balanced")
        
        rfecv = RFECV(
            estimator=estimator,
            step=1,
            cv=cv_strategy,
            scoring="f1_weighted",
            min_features_to_select=1,
        )
        
        rfecv.fit(X_train, y_train)
        
        self.selected_features = X_train.columns[rfecv.support_].tolist()
        
        # Save results
        results = {
            "selected_features_count": int(rfecv.n_features_),
            "selected_features": self.selected_features,
            "cv_scores": rfecv.cv_results_['mean_test_score'].tolist() if hasattr(rfecv, 'cv_results_') else []
        }
        
        (self.outputs_dir / "rfecv_results.json").write_text(json.dumps(results, indent=4))
        (self.outputs_dir / "selected_features.json").write_text(json.dumps(self.selected_features, indent=4))
        
        # We can also save rfecv_curve.csv
        if hasattr(rfecv, 'cv_results_'):
            curve_df = pd.DataFrame({
                "n_features": range(1, len(rfecv.cv_results_['mean_test_score']) + 1),
                "cv_score": rfecv.cv_results_['mean_test_score']
            })
            curve_df.to_csv(self.outputs_dir / "rfecv_curve.csv", index=False)
        
        return X_train[self.selected_features]

    def transform(self, X_test: pd.DataFrame) -> pd.DataFrame:
        """Filters test data to selected features (MUST be called after fit_transform)."""
        if not self.selected_features:
            raise ValueError("RFECV has not been fitted yet.")
            
        missing = [f for f in self.selected_features if f not in X_test.columns]
        if missing:
            raise ValueError(f"Missing required features in test set: {missing}")
            
        return X_test[self.selected_features]
