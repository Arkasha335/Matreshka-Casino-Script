import glob, json, math, os, sys, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions
from engine_mirror import PrngDetectorMirror

sessions = load_all_unique_sessions()

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
                'feats': feats,
                'target': target,
                'outcome': o,
            })
        hist.append({'outcome': o, 'betAmount': 1000, 'betColor': 'RED', 'isWin': True, 'netProfit': 0})

X = np.array([d['feats'] for d in dataset])
y = np.array([d['target'] for d in dataset])

print(f"Training Ridge-Regularized Logistic Head on {X.shape[0]} spins, {X.shape[1]} features...")

scaler = StandardScaler()
X_s = scaler.fit_transform(X)

# C=0.05 provides optimal L2 regularization (penalty alpha = 1 / (2*C) = 10.0)
clf = LogisticRegression(C=0.05, penalty='l2', solver='lbfgs', random_state=42)
clf.fit(X_s, y)

weights = clf.coef_[0].tolist()
bias = float(clf.intercept_[0])
mean = scaler.mean_.tolist()
scale = scaler.scale_.tolist()

print("\n--- Model Parameters ---")
print(f"Bias: {bias:+.6f}")
print("Top 5 Positive Weights (Favor RED):")
pos_w = sorted(enumerate(weights), key=lambda x: -x[1])[:5]
for idx, w in pos_w:
    print(f"  Feature {idx:2d}: {w:+.6f}")

print("Top 5 Negative Weights (Favor BLACK):")
neg_w = sorted(enumerate(weights), key=lambda x: x[1])[:5]
for idx, w in neg_w:
    print(f"  Feature {idx:2d}: {w:+.6f}")

# Export weights json
v16_2_weights = {
    'version': '16.2-APEX-Regularized',
    'timestamp': '2026-11-21T15:00:00Z',
    'scaler': {
        'mean': [round(m, 6) for m in mean],
        'scale': [round(s, 6) for s in scale]
    },
    'weights': {
        'w': [round(w, 6) for w in weights],
        'b': round(bias, 6)
    },
    'theta': 0.04
}

out_path = 'lib/engine/neural_weights_v16.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(v16_2_weights, f, indent=2)
print(f"\nSaved v16.2 weights to {out_path}!")
