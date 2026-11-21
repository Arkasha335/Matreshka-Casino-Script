import glob, json, math, os, sys, warnings
warnings.filterwarnings('ignore')
from collections import defaultdict
import numpy as np
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions
from engine_mirror import PrngDetectorMirror

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

dataset = []
for s_idx, s in enumerate(sessions):
    outs = s['outcomes']
    hist = []
    for o in outs:
        if len(hist) >= 10 and o in ('RED', 'BLACK'):
            feats = PrngDetectorMirror.extract_features(hist)
            target = 1 if o == 'RED' else 0
            dataset.append({
                'session_id': s_idx,
                'is_bot': (s['source'] == 'bot_log'),
                'is_user': ('session_20261119_223110' in s['file']),
                'feats': feats,
                'target': target,
                'outcome': o,
            })
        hist.append({'outcome': o, 'betAmount': 1000, 'betColor': 'RED', 'isWin': True, 'netProfit': 0})

X = np.array([d['feats'] for d in dataset])
y = np.array([d['target'] for d in dataset])
session_ids = np.array([d['session_id'] for d in dataset])
unique_sessions = np.unique(session_ids)

print(f"Dataset: {X.shape[0]} spins, {X.shape[1]} features, {len(unique_sessions)} sessions.")

models_to_test = {
    'Ridge alpha=100.0': RidgeClassifier(alpha=100.0),
    'Ridge alpha=10.0': RidgeClassifier(alpha=10.0),
    'Ridge alpha=1.0': RidgeClassifier(alpha=1.0),
    'Logistic L2 C=0.01': LogisticRegression(C=0.01, penalty='l2', solver='lbfgs'),
    'Logistic L2 C=0.1': LogisticRegression(C=0.1, penalty='l2', solver='lbfgs'),
    'Logistic L2 C=1.0': LogisticRegression(C=1.0, penalty='l2', solver='lbfgs'),
    'MLP (8,) alpha=10.0': MLPClassifier(hidden_layer_sizes=(8,), alpha=10.0, max_iter=150, random_state=42),
    'MLP (12,) alpha=5.0': MLPClassifier(hidden_layer_sizes=(12,), alpha=5.0, max_iter=150, random_state=42),
}

print("\n" + "="*85)
print(f"{'Model Name':25s} | {'LOSO Win Rate':20s} | {'User Test Win Rate':20s}")
print("="*85)

for m_name, model in models_to_test.items():
    correct = 0
    total = 0
    user_correct = 0
    user_total = 0
    
    for s_id in unique_sessions:
        train_mask = (session_ids != s_id)
        test_mask = (session_ids == s_id)
        
        X_train, y_train = X[train_mask], y[train_mask]
        X_test, y_test = X[test_mask], y[test_mask]
        
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        model.fit(X_train_s, y_train)
        preds = model.predict(X_test_s)
        
        s_corr = int(np.sum(preds == y_test))
        correct += s_corr
        total += len(y_test)
        
        is_user_sess = any(d['is_user'] for d in [dataset[i] for i in np.where(test_mask)[0]])
        if is_user_sess:
            user_correct += s_corr
            user_total += len(y_test)
            
    print(f"{m_name:25s} | {correct:4d}/{total:4d} ({correct/total*100:5.2f}%) | {user_correct:3d}/{user_total:3d} ({user_correct/user_total*100:5.2f}%)")
print("="*85)
