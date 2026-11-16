"""
Simulation and Beta-Test of v16.0 APEX-Neural Gated Engine vs v15.0, v15.1, v15.2.
Evaluates Financial Metrics: Net Profit, Resets, Max Step, Avg Closing Step, Avg Bet.
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

# Train production APEX-Neural model
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

mlp = MLPClassifier(hidden_layer_sizes=(24, 12), activation='tanh', alpha=0.1, max_iter=250, random_state=42)
mlp.fit(X_scaled, y)

def make_v16_predictor(meta_lookup, default_fn):
    def predict_v16(hist):
        # Find if this state is in meta
        nz = [h for h in hist if h != 'ZERO']
        if len(nz) < 3 or len(hist) < 4:
            return default_fn(hist)

        # Build feature vector
        feats = []
        for k in range(1, 9):
            if len(nz) >= k: feats.append(1.0 if nz[-k] == 'RED' else -1.0)
            else: feats.append(0.0)

        cur_color = nz[-1]
        streak = 1
        for k in range(len(nz) - 2, -1, -1):
            if nz[k] == cur_color: streak += 1
            else: break
        signed_streak = streak if cur_color == 'RED' else -streak
        feats.append(float(signed_streak))
        feats.append(float(streak))
        feats.append(1.0 if streak == 1 else 0.0)
        feats.append(1.0 if streak == 2 else 0.0)
        feats.append(1.0 if streak == 3 else 0.0)
        feats.append(1.0 if streak >= 4 else 0.0)

        for w in [4, 6, 8, 12, 16]:
            sub = nz[-w:]
            if len(sub) >= 2:
                trans = sum(1 for i in range(1, len(sub)) if sub[i] != sub[i-1])
                feats.append(trans / (len(sub) - 1))
            else: feats.append(0.5)

        for w in [8, 16, 24]:
            sub = nz[-w:]
            if sub: feats.append(sum(1 for x in sub if x == 'RED') / len(sub))
            else: feats.append(0.5)

        z10 = sum(1 for x in hist[-10:] if x == 'ZERO')
        z25 = sum(1 for x in hist[-25:] if x == 'ZERO')
        feats.append(float(z10))
        feats.append(float(z25))

        spins_since_zero = 0
        for k in range(len(hist) - 1, -1, -1):
            if hist[k] == 'ZERO': break
            spins_since_zero += 1
        feats.append(float(min(spins_since_zero, 30)))

        # Running transition stats
        pair_cont, pair_break = 1, 1
        s3_cont, s3_break = 1, 1
        alt_same, alt_diff = 1, 1
        for i in range(2, len(nz)):
            ps = 1
            pc = nz[i - 1]
            for j in range(i - 2, -1, -1):
                if nz[j] == pc: ps += 1
                else: break
            actual = nz[i]
            if ps == 2 and (i < 3 or nz[i - 3] != pc):
                if actual == pc: pair_cont += 1
                else: pair_break += 1
            elif ps >= 3:
                if actual == pc: s3_cont += 1
                else: s3_break += 1
            elif ps == 1:
                if actual == nz[i - 1]: alt_same += 1
                else: alt_diff += 1

        feats.append(pair_cont / (pair_cont + pair_break))
        feats.append(s3_break / (s3_cont + s3_break))
        feats.append(alt_diff / (alt_same + alt_diff))

        feats.append(1.0 if (len(nz) >= 3 and nz[-1] == nz[-3] and nz[-1] != nz[-2]) else 0.0)
        feats.append(1.0 if (len(nz) >= 3 and nz[-2] == nz[-3] and nz[-1] != nz[-2]) else 0.0)

        f_scaled = scaler.transform([feats])
        prob_red = mlp.predict_proba(f_scaled)[0, 1]
        conf = abs(prob_red - 0.5)

        # Gated Decision:
        # If neural net is confident (|p - 0.5| >= 0.08), follow neural net!
        # Otherwise fall back to v15.2 adaptive transition!
        if conf >= 0.08:
            return 'RED' if prob_red >= 0.5 else 'BLACK'
        else:
            return default_fn(hist)

    return predict_v16

predict_v16_gated = make_v16_predictor(meta, predict_v15_2)

# Run full financial simulation of v16.0 vs v15.0, v15.1, v15.2
print("\n" + "="*115)
print(" FINANCIAL COMPARISON: v15.0 vs v15.1 vs v15.2 vs v16.0-BETA (All 48 Sessions, Capital = 7.5M ₽)")
print("="*115)
print(f"{'Engine Version':<27} {'Net Profit (₽)':>16} {'Win Sess':>10} {'WR (%)':>8} {'Avg Step':>9} {'Max Step':>9} {'Avg Bet (₽)':>12} {'Max DD (₽)':>14} {'Resets':>8} {'Busts':>6}")
print("-" * 123)

versions = [
    ('v15.0 FINAL APEX', predict_v15_0, get_cfg_v15_0),
    ('v15.1 Commercial Farm', predict_v15_1, get_cfg_v15_1_2),
    ('v15.2 Synthesized Farm', predict_v15_2, get_cfg_v15_1_2),
    ('v16.0-BETA Neuro-Gated', predict_v16_gated, get_cfg_v15_1_2),
]

for v_name, p_fn, c_fn in versions:
    tot_net = 0
    win_sess = 0
    all_wins = 0
    all_losses = 0
    all_bets = []
    all_closing_steps = []
    max_step_overall = 1
    max_dd_overall = 0
    tot_resets = 0
    tot_busts = 0

    for s in sessions:
        res = simulate_session(s['outcomes'], p_fn, c_fn, init_bank=7_500_000, profile='APEX_IDEAL')
        tot_net += res['net_profit']
        if res['net_profit'] > 0: win_sess += 1
        all_wins += res['wins']
        all_losses += res['losses']
        if res['avg_bet'] > 0: all_bets.append(res['avg_bet'])
        if res['avg_win_step'] > 0: all_closing_steps.append(res['avg_win_step'])
        if res['max_step'] > max_step_overall: max_step_overall = res['max_step']
        if res['max_dd'] > max_dd_overall: max_dd_overall = res['max_dd']
        tot_resets += res['resets']
        if res['is_bust']: tot_busts += 1

    overall_wr = (all_wins / (all_wins + all_losses) * 100) if (all_wins + all_losses) else 0
    overall_avg_step = (sum(all_closing_steps) / len(all_closing_steps)) if all_closing_steps else 0
    overall_avg_bet = (sum(all_bets) / len(all_bets)) if all_bets else 0

    print(f"{v_name:<27} {tot_net:>+16,.0f} {win_sess:>6}/{len(sessions):<3} {overall_wr:>7.2f}% {overall_avg_step:>9.2f} {max_step_overall:>9} {overall_avg_bet:>12,.0f} {max_dd_overall:>14,.0f} {tot_resets:>8} {tot_busts:>6}")
