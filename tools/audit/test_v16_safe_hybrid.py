"""
Testing Safe Hybrid Architectures for v16.0:
Testing Neural Network with:
1) Fallback = v15.1 (Robust Rule MPD)
2) Fallback = v15.2 (Adaptive Empirical)
Across thresholds theta in [0.06, 0.08, 0.10, 0.12, 0.15]
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_1, predict_v15_2, get_cfg_v15_1_2, simulate_session
from research_neural_v16 import extract_features_and_labels
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sessions = load_all_unique_sessions()
X, y, sess_ids, meta = extract_features_and_labels(sessions)
unique_sessions = np.unique(sess_ids)

print("Precomputing out-of-sample probabilities across 48 folds...")
probs_dict = {}

for s_idx in unique_sessions:
    tr = (sess_ids != s_idx)
    te = (sess_ids == s_idx)

    sc = StandardScaler()
    X_tr = sc.fit_transform(X[tr])
    X_te = sc.transform(X[te])

    clf = MLPClassifier(hidden_layer_sizes=(24, 12), activation='tanh', alpha=0.1, max_iter=200, random_state=42)
    clf.fit(X_tr, y[tr])
    probs = clf.predict_proba(X_te)[:, 1]

    test_indices = np.where(te)[0]
    for i, idx in enumerate(test_indices):
        h_len = len(meta[idx]['hist_copy'])
        probs_dict[(s_idx, h_len)] = probs[i]

def run_policy(fallback_name, fallback_fn, theta):
    preds_map = {}
    for (s_idx, h_len), p in probs_dict.items():
        conf = abs(p - 0.5)
        if conf >= theta:
            pred = 'RED' if p >= 0.5 else 'BLACK'
        else:
            # We need history
            pred = None # resolved dynamically in sim
        preds_map[(s_idx, h_len)] = (p, conf)

    def make_pred_fn(s_idx):
        def pred_fn(hist):
            h_len = len(hist)
            if (s_idx, h_len) in preds_map:
                p, conf = preds_map[(s_idx, h_len)]
                if conf >= theta:
                    return 'RED' if p >= 0.5 else 'BLACK'
            return fallback_fn(hist)
        return pred_fn

    res_list = []
    for s_idx, s in enumerate(sessions):
        p_fn = make_pred_fn(s_idx)
        res_list.append(simulate_session(s['outcomes'], p_fn, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL'))

    tot_net = sum(r['net_profit'] for r in res_list)
    win_sess = sum(1 for r in res_list if r['net_profit'] > 0)
    all_w = sum(r['wins'] for r in res_list)
    all_l = sum(r['losses'] for r in res_list)
    overall_wr = (all_w / (all_w + all_l) * 100) if (all_w + all_l) else 0
    all_steps = [r['avg_win_step'] for r in res_list if r['avg_win_step'] > 0]
    avg_step = sum(all_steps) / len(all_steps) if all_steps else 0
    max_step = max(r['max_step'] for r in res_list)
    max_dd = max(r['max_dd'] for r in res_list)
    tot_resets = sum(r['resets'] for r in res_list)

    return {
        'fallback': fallback_name,
        'theta': theta,
        'net': tot_net,
        'win_sess': win_sess,
        'wr': overall_wr,
        'avg_step': avg_step,
        'max_step': max_step,
        'max_dd': max_dd,
        'resets': tot_resets
    }

print("\n" + "="*115)
print(" POLICY GRID SEARCH: Neural Network + Fallback (v15.1 vs v15.2) at different theta thresholds")
print("="*115)
print(f"{'Fallback':<15} {'Theta':>7} {'Net Profit (₽)':>16} {'Win Sess':>10} {'WR (%)':>8} {'Avg Step':>9} {'Max Step':>9} {'Max DD (₽)':>14} {'Resets':>8}")
print("-" * 115)

for fb_name, fb_fn in [('v15.1 (Rule)', predict_v15_1), ('v15.2 (Adapt)', predict_v15_2)]:
    for th in [0.06, 0.08, 0.10, 0.12, 0.15]:
        res = run_policy(fb_name, fb_fn, th)
        print(f"{res['fallback']:<15} {res['theta']:>7.2f} {res['net']:>+16,.0f} {res['win_sess']:>6}/{len(sessions):<3} {res['wr']:>7.2f}% {res['avg_step']:>9.2f} {res['max_step']:>9} {res['max_dd']:>14,.0f} {res['resets']:>8}")
