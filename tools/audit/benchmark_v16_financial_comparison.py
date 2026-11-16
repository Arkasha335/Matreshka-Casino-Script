"""
Financial Benchmark of v16.0 APEX-Neural (24-12 MLP + Bayesian Gating)
Simulates all 48 real sessions in Leave-One-Session-Out Cross Validation.
Direct comparison with v15.0, v15.1, v15.2 under identical APEX_FARM profile.
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_0, predict_v15_1, predict_v15_2, get_cfg_v15_0, get_cfg_v15_1_2, simulate_session
from research_v16_neural_engine import extract_advanced_features
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sessions = load_all_unique_sessions()
X, y, sess_ids, meta = extract_advanced_features(sessions)
unique_sessions = np.unique(sess_ids)

print("Precomputing 48-fold LOSO out-of-sample predictions for v16.0 APEX-Neural...")
out_of_sample_preds_v16 = {}

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
        p = probs[i]
        conf = abs(p - 0.5)
        if conf >= 0.08:
            pred = 'RED' if p >= 0.5 else 'BLACK'
        else:
            pred = predict_v15_2(meta[idx]['hist_copy'])
        
        h_len = len(meta[idx]['hist_copy'])
        out_of_sample_preds_v16[(s_idx, h_len)] = pred

def make_v16_predictor(s_idx):
    def predict_v16(hist):
        h_len = len(hist)
        if (s_idx, h_len) in out_of_sample_preds_v16:
            return out_of_sample_preds_v16[(s_idx, h_len)]
        return predict_v15_2(hist)
    return predict_v16

print("\n" + "="*120)
print(" FINANCIAL AUDIT: v15.0 vs v15.1 vs v15.2 vs v16.0 APEX-Neural (All 48 Sessions, Capital = 7.5M ₽)")
print("="*120)
print(f"{'Engine Version':<28} {'Net Profit (₽)':>16} {'Win Sess':>10} {'WR (%)':>8} {'Avg Step':>9} {'Max Step':>9} {'Avg Bet (₽)':>12} {'Max DD (₽)':>14} {'Resets':>8} {'Busts':>6}")
print("-" * 128)

# 1. v15.0
r_v15_0 = []
for s in sessions:
    r_v15_0.append(simulate_session(s['outcomes'], predict_v15_0, get_cfg_v15_0, init_bank=7_500_000, profile='APEX_IDEAL'))

# 2. v15.1
r_v15_1 = []
for s in sessions:
    r_v15_1.append(simulate_session(s['outcomes'], predict_v15_1, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL'))

# 3. v15.2
r_v15_2 = []
for s in sessions:
    r_v15_2.append(simulate_session(s['outcomes'], predict_v15_2, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL'))

# 4. v16.0 LOSO
r_v16_0 = []
for s_idx, s in enumerate(sessions):
    p_fn = make_v16_predictor(s_idx)
    r_v16_0.append(simulate_session(s['outcomes'], p_fn, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL'))

for v_name, res_list in [
    ('v15.0 FINAL APEX', r_v15_0),
    ('v15.1 Commercial Farm', r_v15_1),
    ('v15.2 Synthesized Farm', r_v15_2),
    ('v16.0 APEX-Neural (LOSO)', r_v16_0),
]:
    tot_net = sum(r['net_profit'] for r in res_list)
    win_sess = sum(1 for r in res_list if r['net_profit'] > 0)
    all_w = sum(r['wins'] for r in res_list)
    all_l = sum(r['losses'] for r in res_list)
    overall_wr = (all_w / (all_w + all_l) * 100) if (all_w + all_l) else 0
    all_bets = [r['avg_bet'] for r in res_list if r['avg_bet'] > 0]
    avg_bet = sum(all_bets) / len(all_bets) if all_bets else 0
    all_steps = [r['avg_win_step'] for r in res_list if r['avg_win_step'] > 0]
    avg_step = sum(all_steps) / len(all_steps) if all_steps else 0
    max_step = max(r['max_step'] for r in res_list)
    max_dd = max(r['max_dd'] for r in res_list)
    tot_resets = sum(r['resets'] for r in res_list)
    tot_busts = sum(1 for r in res_list if r['is_bust'])

    print(f"{v_name:<28} {tot_net:>+16,.0f} {win_sess:>6}/{len(sessions):<3} {overall_wr:>7.2f}% {avg_step:>9.2f} {max_step:>9} {avg_bet:>12,.0f} {max_dd:>14,.0f} {tot_resets:>8} {tot_busts:>6}")
