"""
v16.0 Architecture Optimization:
Fusing Neural Feature Learning with Adaptive Bayesian Markov Transitions.
Goal: Maximize Winrate on BOTH Real Bot Sessions and Full Dataset,
while minimizing Terminal Sequence Losses.
"""
import glob, json, math, os, sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_1, predict_v15_2, simulate_session, get_cfg_v15_1_2
from research_neural_v16 import extract_features_and_labels

from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sessions = load_all_unique_sessions()
X, y, sess_ids, meta = extract_features_and_labels(sessions)

# Train an APEX-Neural weights model on the full historical dataset to evaluate feature importances & calibration
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

mlp = MLPClassifier(hidden_layer_sizes=(24, 12), activation='tanh', alpha=0.1, max_iter=250, random_state=42)
mlp.fit(X_scaled, y)

print("MLP trained successfully.")

# Now test different hybrid decision policies in Leave-One-Session-Out CV:
unique_sessions = np.unique(sess_ids)

policies = [
    'v15.2_Baseline',
    'Neural_Pure',
    'Gated_V16_T10 (Neural if |p-0.5|>=0.10 else v15.2)',
    'Gated_V16_T08 (Neural if |p-0.5|>=0.08 else v15.2)',
    'Gated_V16_T06 (Neural if |p-0.5|>=0.06 else v15.2)',
    'Gated_V16_T04 (Neural if |p-0.5|>=0.04 else v15.2)',
    'Consensus_V16 (Bet when Neural & v15.2 agree, else hedge)'
]

results = {p: [] for p in policies}
bot_results = {p: [] for p in policies}

for s_idx in unique_sessions:
    train_mask = (sess_ids != s_idx)
    test_mask = (sess_ids == s_idx)

    X_tr, y_tr = X[train_mask], y[train_mask]
    X_te, y_te = X[test_mask], y[test_mask]

    sc = StandardScaler()
    X_tr_s = sc.fit_transform(X_tr)
    X_te_s = sc.transform(X_te)

    clf = MLPClassifier(hidden_layer_sizes=(24, 12), activation='tanh', alpha=0.1, max_iter=200, random_state=42)
    clf.fit(X_tr_s, y_tr)
    probs = clf.predict_proba(X_te_s)[:, 1]

    test_indices = np.where(test_mask)[0]
    for i, idx in enumerate(test_indices):
        p_neural = probs[i]
        pred_neural = 1 if p_neural >= 0.5 else 0
        conf_neural = abs(p_neural - 0.5)

        p_v15_2_str = predict_v15_2(meta[idx]['hist_copy'])
        pred_v15_2 = 1 if p_v15_2_str == 'RED' else 0

        target = y_te[i]
        is_bot = meta[idx]['is_bot']

        # Decisions per policy
        d_v15_2 = pred_v15_2
        d_neural = pred_neural
        d_gated10 = pred_neural if conf_neural >= 0.10 else pred_v15_2
        d_gated08 = pred_neural if conf_neural >= 0.08 else pred_v15_2
        d_gated06 = pred_neural if conf_neural >= 0.06 else pred_v15_2
        d_gated04 = pred_neural if conf_neural >= 0.04 else pred_v15_2
        d_consensus = pred_neural if pred_neural == pred_v15_2 else pred_v15_2

        pol_decisions = {
            'v15.2_Baseline': d_v15_2 == target,
            'Neural_Pure': d_neural == target,
            'Gated_V16_T10 (Neural if |p-0.5|>=0.10 else v15.2)': d_gated10 == target,
            'Gated_V16_T08 (Neural if |p-0.5|>=0.08 else v15.2)': d_gated08 == target,
            'Gated_V16_T06 (Neural if |p-0.5|>=0.06 else v15.2)': d_gated06 == target,
            'Gated_V16_T04 (Neural if |p-0.5|>=0.04 else v15.2)': d_gated04 == target,
            'Consensus_V16 (Bet when Neural & v15.2 agree, else hedge)': d_consensus == target
        }

        for p in policies:
            results[p].append(pol_decisions[p])
            if is_bot:
                bot_results[p].append(pol_decisions[p])

print("\n" + "="*95)
print(" POLICY COMPARISON (LOSO-CV OUT-OF-SAMPLE TEST):")
print("="*95)
print(f"{'Policy Name':<55} {'Overall WR':>12} {'Bot WR':>12} {'Overall z':>10}")
print("-" * 95)
for p in policies:
    ov_wr = np.mean(results[p]) * 100
    b_wr = np.mean(bot_results[p]) * 100
    z = (ov_wr - 50.0) / math.sqrt(25.0 / len(results[p]))
    print(f"{p:<55} {ov_wr:>11.2f}% {b_wr:>11.2f}% {z:>+10.2f}")
