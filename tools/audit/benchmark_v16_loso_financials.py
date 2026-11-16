"""
Strict Out-of-Sample Financial Evaluation of v16.0 under Leave-One-Session-Out CV (48 folds).
Ensures zero train/test leakage: each session is played using weights trained EXCLUSIVELY on the other 47 sessions!
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_0, predict_v15_1, predict_v15_2, get_cfg_v15_0, get_cfg_v15_1_2, simulate_session
from research_neural_v16 import extract_features_and_labels
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sessions = load_all_unique_sessions()
X, y, sess_ids, meta = extract_features_and_labels(sessions)

unique_sessions = np.unique(sess_ids)
out_of_sample_preds_v16 = {}

print("Generating strict out-of-sample predictions across 48 folds...")
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
        conf_neural = abs(p_neural - 0.5)
        p_v15_2_str = predict_v15_2(meta[idx]['hist_copy'])
        
        # Gated Decision:
        if conf_neural >= 0.10:
            pred = 'RED' if p_neural >= 0.5 else 'BLACK'
        else:
            pred = p_v15_2_str

        # Store prediction by (sess_idx, hist_len)
        h_len = len(meta[idx]['hist_copy'])
        out_of_sample_preds_v16[(s_idx, h_len)] = pred

def make_loso_v16_predictor(s_idx):
    def predict_loso(hist):
        h_len = len(hist)
        if (s_idx, h_len) in out_of_sample_preds_v16:
            return out_of_sample_preds_v16[(s_idx, h_len)]
        return predict_v15_2(hist)
    return predict_loso

# Now simulate session by session strictly out of sample
tot_net_16 = 0
win_sess_16 = 0
all_wins_16 = 0
all_losses_16 = 0
all_bets_16 = []
all_closing_steps_16 = []
max_step_overall_16 = 1
max_dd_overall_16 = 0
tot_resets_16 = 0
tot_busts_16 = 0

for s_idx, s in enumerate(sessions):
    p_fn = make_loso_v16_predictor(s_idx)
    res = simulate_session(s['outcomes'], p_fn, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL')
    tot_net_16 += res['net_profit']
    if res['net_profit'] > 0: win_sess_16 += 1
    all_wins_16 += res['wins']
    all_losses_16 += res['losses']
    if res['avg_bet'] > 0: all_bets_16.append(res['avg_bet'])
    if res['avg_win_step'] > 0: all_closing_steps_16.append(res['avg_win_step'])
    if res['max_step'] > max_step_overall_16: max_step_overall_16 = res['max_step']
    if res['max_dd'] > max_dd_overall_16: max_dd_overall_16 = res['max_dd']
    tot_resets_16 += res['resets']
    if res['is_bust']: tot_busts_16 += 1

overall_wr_16 = (all_wins_16 / (all_wins_16 + all_losses_16) * 100) if (all_wins_16 + all_losses_16) else 0
overall_avg_step_16 = (sum(all_closing_steps_16) / len(all_closing_steps_16)) if all_closing_steps_16 else 0
overall_avg_bet_16 = (sum(all_bets_16) / len(all_bets_16)) if all_bets_16 else 0

print("\n" + "="*115)
print(" STRICT OUT-OF-SAMPLE FINANCIAL BENCHMARK (48-FOLD LEAVE-ONE-SESSION-OUT CV)")
print("="*115)
print(f"{'Engine Version':<27} {'Net Profit (₽)':>16} {'Win Sess':>10} {'WR (%)':>8} {'Avg Step':>9} {'Max Step':>9} {'Avg Bet (₽)':>12} {'Max DD (₽)':>14} {'Resets':>8} {'Busts':>6}")
print("-" * 123)
print(f"{'v16.0-LOSO (Out-of-Sample)':<27} {tot_net_16:>+16,.0f} {win_sess_16:>6}/{len(sessions):<3} {overall_wr_16:>7.2f}% {overall_avg_step_16:>9.2f} {max_step_overall_16:>9} {overall_avg_bet_16:>12,.0f} {max_dd_overall_16:>14,.0f} {tot_resets_16:>8} {tot_busts_16:>6}")
