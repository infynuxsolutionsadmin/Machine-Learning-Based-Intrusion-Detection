import joblib
import pickle
import os
import time

def inspect_model(filepath):
    result = {'filepath': filepath}
    try:
        stat = os.stat(filepath)
        result['size'] = stat.st_size
        result['mtime'] = time.ctime(stat.st_mtime)
        try:
            model = joblib.load(filepath)
            result['serialization'] = 'joblib'
        except:
            with open(filepath, 'rb') as f:
                model = pickle.load(f)
            result['serialization'] = 'pickle'
        
        result['class'] = type(model).__name__
        
        if hasattr(model, 'n_features_in_'):
            result['n_features_in_'] = model.n_features_in_
        if hasattr(model, 'feature_names_in_'):
            result['feature_names_in_'] = list(model.feature_names_in_)
        if hasattr(model, 'classes_'):
            result['classes_'] = list(model.classes_)
            
    except Exception as e:
        result['error'] = str(e)
    return result

base_dir = r"C:\Users\divya\OneDrive\Desktop\ML_MANET\backend\models"
dirs_to_check = ['baseline', 'expanded_dataset', '']

for d in dirs_to_check:
    target_dir = os.path.join(base_dir, d)
    if not os.path.isdir(target_dir): continue
    for f in os.listdir(target_dir):
        if f.endswith('.pkl'):
            fp = os.path.join(target_dir, f)
            print(inspect_model(fp))

