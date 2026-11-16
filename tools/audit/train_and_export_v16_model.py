"""
Train & Export Production v16.0 APEX-Neural Model.
Trains a 24-12 MLP with Tanh activation on all 48 real sessions.
Exports weights, biases, and standard scaler parameters to JSON for 100% parity implementation in TS and Python.
"""
import glob, json, math, os, sys
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions
from research_neural_v16 import extract_features_and_labels

sessions = load_all_unique_sessions()
print(f"Loading features from {len(sessions)} sessions...")
X, y, sess_ids, meta = extract_features_and_labels(sessions)
print(f"Dataset: {X.shape[0]} samples with {X.shape[1]} features.")

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

clf = MLPClassifier(hidden_layer_sizes=(24, 12), activation='tanh', alpha=0.1, max_iter=300, random_state=42)
clf.fit(X_scaled, y)
train_acc = clf.score(X_scaled, y) * 100
print(f"Model trained. Convergence iterations: {clf.n_iter_}, In-sample accuracy: {train_acc:.2f}%")

# Extract weights and biases
# coefs_[0]: (30, 24), intercepts_[0]: (24,)
# coefs_[1]: (24, 12), intercepts_[1]: (12,)
# coefs_[2]: (12, 1),  intercepts_[2]: (1,)
model_dict = {
    'version': '16.0-APEX-NEURAL',
    'input_dim': int(X.shape[1]),
    'hidden_layers': [24, 12],
    'activation': 'tanh',
    'theta': 0.06,
    'scaler': {
        'mean': [round(float(v), 8) for v in scaler.mean_],
        'scale': [round(float(v), 8) for v in scaler.scale_]
    },
    'weights': {
        'w1': [[round(float(v), 8) for v in row] for row in clf.coefs_[0]],
        'b1': [round(float(v), 8) for v in clf.intercepts_[0]],
        'w2': [[round(float(v), 8) for v in row] for row in clf.coefs_[1]],
        'b2': [round(float(v), 8) for v in clf.intercepts_[1]],
        'w3': [[round(float(v), 8) for v in row] for row in clf.coefs_[2]],
        'b3': [round(float(v), 8) for v in clf.intercepts_[2]]
    }
}

out_path_ts = os.path.join(os.path.dirname(__file__), '..', '..', 'lib', 'engine', 'neural_weights_v16.json')
out_path_audit = os.path.join(os.path.dirname(__file__), 'neural_weights_v16.json')

with open(out_path_ts, 'w', encoding='utf-8') as f:
    json.dump(model_dict, f, indent=2)

with open(out_path_audit, 'w', encoding='utf-8') as f:
    json.dump(model_dict, f, indent=2)

print(f"Exported model weights to:\n  - {out_path_ts}\n  - {out_path_audit}")
