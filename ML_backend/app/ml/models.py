from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from xgboost import XGBClassifier
from catboost import CatBoostClassifier

def get_models(random_state: int = 42):
    """
    Returns baseline models configured with basic class imbalance handling.
    No deep hyperparameter searching is performed to avoid overfitting the extremely small dataset.
    """
    return {
        "RandomForest": RandomForestClassifier(
            n_estimators=100, 
            random_state=random_state, 
            class_weight="balanced"
        ),
        "XGBoost": XGBClassifier(
            use_label_encoder=False, 
            eval_metric="logloss", 
            random_state=random_state,
            scale_pos_weight=7.0 # Approximated from 28/4 ratio
        ),
        "CatBoost": CatBoostClassifier(
            iterations=100, 
            random_state=random_state, 
            verbose=0,
            auto_class_weights="Balanced"
        ),
        "SVM": SVC(
            kernel="rbf", 
            probability=True, 
            random_state=random_state, 
            class_weight="balanced"
        ),
        "MLP": MLPClassifier(
            hidden_layer_sizes=(16, 8), 
            max_iter=500, 
            random_state=random_state
            # MLP in sklearn does not natively support class_weight.
        )
    }
