"""
Strict Leave-One-Session-Out (LOSO) Cross-Validation Benchmark for v16.1 APEX-Neural
Every session is evaluated ONLY on a model trained on the other 48 sessions.
Zero data leakage, 100% out-of-sample empirical rigor.
"""
import glob, json, math, os, sys
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_2, get_cfg_v15_1_2, simulate_session
from evaluate_v16_1_production import extract_features_v16_1

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions for LOSO benchmark.")

# Pre-extract all features
session_data = []
for s_idx, sess in enumerate(sessions):
    outs = sess['outcomes']
    hist = []
    feats_list = []
    y_list = []
    for t, out in enumerate(outs):
        if out in ('RED', 'BLACK') and len(hist) >= 4:
            nz = [h for h in hist if h != 'ZERO']
            if len(nz) >= 3:
                f = extract_features_v16_1(hist)
                if f:
                    feats_list.append((t, f, 1 if out == 'RED' else 0))
        hist.append(out)
    session_data.append({
        'sess': sess,
        'feats_list': feats_list
    })

print("Pre-extraction complete. Starting 49-fold LOSO CV...")

total_spins = 0
total_wins = 0
total_profit = 0
max_step_overall = 0
win_steps = []
avg_bets = []
total_resets = 0

fresh_res = None

for test_idx in range(len(sessions)):
    # Prepare training set: all sessions except test_idx
    X_train = []
    y_train = []
    for s_idx in range(len(sessions)):
        if s_idx == test_idx: continue
        for _, f, target in session_data[s_idx]['feats_list']:
            X_train.append(f)
            y_train.append(target)
            
    X_train = np.array(X_train, dtype=np.float32)
    y_train = np.array(y_train, dtype=np.int32)
    
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_train)
    
    clf = MLPClassifier(hidden_layer_sizes=(24, 12), activation='tanh', alpha=0.1, max_iter=200, random_state=42)
    clf.fit(X_tr_s, y_train)
    
    # Build out-of-sample predictor function for test session
    mu = scaler.mean_
    scale = scaler.scale_
    w1, b1 = clf.coefs_[0], clf.intercepts_[0]
    w2, b2 = clf.coefs_[1], clf.intercepts_[1]
    w3, b3 = clf.coefs_[2], clf.intercepts_[2]
    
    def test_predict(history):
        raw = [h if isinstance(h, str) else (h.get('outcome', '') if isinstance(h, dict) else getattr(h, 'outcome', '')) for h in history]
        nz = [x for x in raw if x != 'ZERO']
        if len(nz) < 3:
            return nz[-1] if nz else 'RED'
        
        cur_c = nz[-1]
        opp_c = 'BLACK' if cur_c == 'RED' else 'RED'
        
        s = 1
        for k in range(len(nz)-2, -1, -1):
            if nz[k] == cur_c: s += 1
            else: break
            
        prev_s = 1
        idx_prev = len(nz) - 1 - s
        if idx_prev >= 0:
            for k in range(idx_prev - 1, -1, -1):
                if nz[k] == opp_c: prev_s += 1
                else: break
                
        w24 = nz[-24:]
        st = []
        if w24:
            tc = w24[0]; tl = 1
            for j in range(1, len(w24)):
                if w24[j] == tc: tl += 1
                else:
                    if tc == cur_c: st.append(tl)
                    tc = w24[j]; tl = 1
            if tc == cur_c: st.append(tl)
        avg_cur = sum(st) / len(st) if st else 1.8
        sat_ratio = s / max(1.0, avg_cur)
        
        feats = extract_features_v16_1(history)
        if feats is not None:
            z = [(feats[i] - mu[i]) / scale[i] for i in range(30)]
            h1 = np.tanh(np.dot(z, w1) + b1)
            h2 = np.tanh(np.dot(h1, w2) + b2)
            out_val = np.dot(h2, w3)[0] + b3[0]
            p_red = 1.0 / (1.0 + math.exp(-out_val))
        else:
            p_red = 0.5
            
        # Dynamic Gating:
        # A. Couplet Break Law
        if s == 2 and prev_s == 2:
            if cur_c == 'RED' and p_red < 0.68: return 'BLACK'
            elif cur_c == 'BLACK' and p_red > 0.32: return 'RED'
            
        # B. Streak Saturation Law
        if s >= 2 and sat_ratio >= 1.0:
            if cur_c == 'RED' and p_red < 0.65: return 'BLACK'
            elif cur_c == 'BLACK' and p_red > 0.35: return 'RED'
            
        # C. Streak Young / Continuation Law
        fast_alt = sum(1 for j in range(1, len(nz[-4:])) if nz[-4:][j] != nz[-4:][j-1]) / max(1, len(nz[-4:])-1) if len(nz) >= 4 else 0.5
        if s == 1 and sat_ratio < 0.60 and fast_alt < 0.70:
            if cur_c == 'RED' and p_red >= 0.42: return 'RED'
            elif cur_c == 'BLACK' and p_red <= 0.58: return 'BLACK'
            
        # D. Standard Neural
        if abs(p_red - 0.5) >= 0.06:
            return 'RED' if p_red >= 0.5 else 'BLACK'
            
        # E. Fallback
        return predict_v15_2(history)
        
    test_sess = sessions[test_idx]
    r = simulate_session(test_sess['outcomes'], test_predict, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL')
    
    total_spins += r['total_spins']
    total_wins += r['wins']
    total_profit += r['net_profit']
    total_resets += r['resets']
    if r['max_step'] > max_step_overall:
        max_step_overall = r['max_step']
    if r['avg_win_step'] > 0:
        win_steps.append(r['avg_win_step'])
    if r['avg_bet'] > 0:
        avg_bets.append(r['avg_bet'])
        
    if '20261117' in test_sess['file']:
        fresh_res = r
        print(f"  -> Fresh Session (17.11) Out-of-Sample: WinRate={r['wr']:.2f}% | MaxStep={r['max_step']} | MaxDD={r['max_dd']:,} | PnL={r['net_profit']:+,} RUB")

avg_winrate = (total_wins / total_spins) * 100 if total_spins > 0 else 0
avg_bet = np.mean(avg_bets) if avg_bets else 0
avg_close_step = np.mean(win_steps) if win_steps else 0

print(f"\n==========================================")
print(f"FINAL v16.1 APEX-NEURAL TRUE OUT-OF-SAMPLE (LOSO) RESULTS:")
print(f"==========================================")
print(f"  All 49 Sessions Out-of-Sample Win Rate: {avg_winrate:.2f}% (Wins: {total_wins}/{total_spins})")
print(f"  Total Out-of-Sample PnL: {total_profit:+,} RUB")
print(f"  Max Step Reached Across All Sessions: {max_step_overall}")
print(f"  Terminal Resets Across All Sessions: {total_resets}")
print(f"  Average Closing Step: {avg_close_step:.2f}")
print(f"  Average Bet: {avg_bet:,.0f} RUB")
print(f"==========================================")
