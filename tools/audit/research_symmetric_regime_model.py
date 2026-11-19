"""
Research Symmetric Regime Predictor: P(Continue vs Break) conditioned on Streak-Mood & Previous Streak Length.
Evaluates accuracy on:
- Streak = 1 (Single -> Pair vs Alternation)
- Streak = 2 (Pair -> Triple vs Pair-Break)
- Streak >= 3 (Deep Streak -> Push vs Bounce)
Across all 49 sessions (6,433 spins).
"""
import glob, json, math, os, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

# Build symmetric dataset:
# At each non-zero spin t (where t >= 4 and len(nz) >= 3):
# Feature vector x describes the state from the perspective of the CURRENT active streak:
# Target: y = 1 if current streak continues, y = 0 if current streak breaks (switches color).
# If y_pred == 1 -> recommendation = cur_color
# If y_pred == 0 -> recommendation = opp_color

X_list = []
y_list = []
sess_ids = []
meta_list = []

for s_idx, sess in enumerate(sessions):
    outs = sess['outcomes']
    hist = []
    
    for t, out in enumerate(outs):
        if out in ('RED', 'BLACK') and len(hist) >= 4:
            nz = [h for h in hist if h != 'ZERO']
            if len(nz) >= 3:
                cur_col = nz[-1]
                opp_col = 'BLACK' if cur_col == 'RED' else 'RED'
                
                # Current active streak
                s = 1
                for k in range(len(nz) - 2, -1, -1):
                    if nz[k] == cur_col: s += 1
                    else: break
                    
                # Previous completed streak of opposite color
                prev_s = 1
                idx_prev = len(nz) - 1 - s
                if idx_prev >= 0:
                    for k in range(idx_prev - 1, -1, -1):
                        if nz[k] == opp_col: prev_s += 1
                        else: break
                else:
                    prev_s = 1
                    
                # 2nd previous completed streak (same color as current)
                prev2_s = 1
                idx_prev2 = idx_prev - prev_s
                if idx_prev2 >= 0:
                    for k in range(idx_prev2 - 1, -1, -1):
                        if nz[k] == cur_col: prev2_s += 1
                        else: break
                else:
                    prev2_s = 1

                # Rolling streak statistics (window 24)
                w24 = nz[-24:]
                st_cur, st_opp = [], []
                if w24:
                    tc = w24[0]; tl = 1
                    for j in range(1, len(w24)):
                        if w24[j] == tc: tl += 1
                        else:
                            if tc == cur_col: st_cur.append(tl)
                            else: st_opp.append(tl)
                            tc = w24[j]; tl = 1
                    if tc == cur_col: st_cur.append(tl)
                    else: st_opp.append(tl)

                avg_cur = sum(st_cur) / len(st_cur) if st_cur else 1.5
                avg_opp = sum(st_opp) / len(st_opp) if st_opp else 1.5
                max_cur = max(st_cur) if st_cur else 2
                max_opp = max(st_opp) if st_opp else 2
                
                # Alternation rates in local windows
                alt_rates = []
                for w in [4, 6, 8, 12, 16]:
                    sub = nz[-w:]
                    if len(sub) >= 2:
                        trans = sum(1 for j in range(1, len(sub)) if sub[j] != sub[j-1])
                        alt_rates.append(trans / (len(sub) - 1))
                    else:
                        alt_rates.append(0.5)
                        
                # Current color ratio in local windows (dominance of current color)
                col_ratios = []
                for w in [8, 16, 24]:
                    sub = nz[-w:]
                    if sub:
                        c_cnt = sum(1 for x in sub if x == cur_col)
                        col_ratios.append(c_cnt / len(sub))
                    else:
                        col_ratios.append(0.5)

                # ZERO context
                z10 = sum(1 for x in hist[-10:] if x == 'ZERO')
                z25 = sum(1 for x in hist[-25:] if x == 'ZERO')
                
                # Empirical Bayesian pair / streak transitions from session so far
                pair_cont, pair_break = 1, 1
                s3_cont, s3_break = 1, 1
                alt_same, alt_diff = 1, 1
                for i in range(2, len(nz)):
                    ps = 1
                    pc = nz[i - 1]
                    for j in range(i - 2, -1, -1):
                        if nz[j] == pc: ps += 1
                        else: break
                    actual_nz = nz[i]
                    if ps == 2 and (i < 3 or nz[i - 3] != pc):
                        if actual_nz == pc: pair_cont += 1
                        else: pair_break += 1
                    elif ps >= 3:
                        if actual_nz == pc: s3_cont += 1
                        else: s3_break += 1
                    elif ps == 1:
                        if actual_nz == nz[i - 1]: alt_same += 1
                        else: alt_diff += 1
                
                # Feature Vector: Clean, Normalized, Physically Interpretable
                feats = [
                    # 1. Streak descriptors
                    float(s),                       # Current streak length
                    1.0 if s == 1 else 0.0,         # Is single
                    1.0 if s == 2 else 0.0,         # Is pair
                    1.0 if s == 3 else 0.0,         # Is 3
                    1.0 if s >= 4 else 0.0,         # Is deep >= 4
                    
                    # 2. Previous streak memory
                    float(min(prev_s, 6)),          # Prev streak length
                    1.0 if prev_s == 1 else 0.0,    # Was prev single
                    1.0 if prev_s == 2 else 0.0,    # Was prev pair
                    1.0 if prev_s >= 3 else 0.0,    # Was prev deep
                    float(min(prev2_s, 6)),         # 2nd prev streak length
                    
                    # 3. Average Streak Mood & Relative Length
                    avg_cur,                        # Rolling avg streak of current color
                    avg_opp,                        # Rolling avg streak of opp color
                    avg_cur - avg_opp,              # Asymmetry between colors
                    float(s) / max(1.0, avg_cur),   # Exhaustion ratio: s / avg_cur
                    float(s) / max(1.0, max_cur),   # Saturation ratio: s / max_cur
                    
                    # 4. Alternation frequencies
                    alt_rates[0], alt_rates[1], alt_rates[2], alt_rates[3], alt_rates[4],
                    
                    # 5. Dominance of current color
                    col_ratios[0], col_ratios[1], col_ratios[2],
                    
                    # 6. Empirical Bayesian session rates
                    pair_cont / (pair_cont + pair_break),
                    s3_break / (s3_cont + s3_break),
                    alt_diff / (alt_same + alt_diff),
                    
                    # 7. ZERO clustering
                    float(z10), float(z25),
                ]
                
                # Target: 1 if current streak continues (outcome == cur_col), 0 if breaks
                did_cont = 1 if out == cur_col else 0
                
                X_list.append(feats)
                y_list.append(did_cont)
                sess_ids.append(s_idx)
                meta_list.append({
                    'cur_col': cur_col,
                    'opp_col': opp_col,
                    'outcome': out,
                    'streak': s,
                    'prev_s': prev_s,
                    'is_bot': sess['source'] == 'bot_log'
                })
        
        hist.append(out)

X = np.array(X_list, dtype=np.float32)
y = np.array(y_list, dtype=np.int32)
sess_ids = np.array(sess_ids)

print(f"Total dataset: {X.shape[0]} samples with {X.shape[1]} features across {len(np.unique(sess_ids))} sessions.")
print(f"Global Base P(Continuation) = {np.mean(y)*100:.2f}%, P(Break) = {(1-np.mean(y))*100:.2f}%")

# Test Models in 49-fold Leave-One-Session-Out Cross Validation
unique_sessions = np.unique(sess_ids)

models = [
    ('Logistic Regression (L2=1.0)', LogisticRegression(C=1.0, max_iter=300)),
    ('MLP (20-10, Tanh, alpha=0.2)', MLPClassifier(hidden_layer_sizes=(20, 10), activation='tanh', alpha=0.2, max_iter=200, random_state=42)),
    ('MLP (16-8, Tanh, alpha=0.1)', MLPClassifier(hidden_layer_sizes=(16, 8), activation='tanh', alpha=0.1, max_iter=200, random_state=42)),
]

for m_name, model in models:
    print(f"\n--- Testing {m_name} in 49-fold LOSO CV ---")
    correct_all = []
    correct_s1 = []
    correct_s2 = []
    correct_s3plus = []
    correct_bot = []
    
    for s_idx in unique_sessions:
        tr = (sess_ids != s_idx)
        te = (sess_ids == s_idx)
        
        sc = StandardScaler()
        X_tr = sc.fit_transform(X[tr])
        X_te = sc.transform(X[te])
        
        model.fit(X_tr, y[tr])
        probs_cont = model.predict_proba(X_te)[:, 1]
        
        test_indices = np.where(te)[0]
        for i, idx in enumerate(test_indices):
            p_c = probs_cont[i]
            # If p_c >= 0.50 -> predict Continuation (cur_col)
            # If p_c < 0.50  -> predict Break (opp_col)
            pred_cont = 1 if p_c >= 0.50 else 0
            actual_cont = y[te][i]
            is_correct = (pred_cont == actual_cont)
            
            correct_all.append(is_correct)
            st = meta_list[idx]['streak']
            if st == 1: correct_s1.append(is_correct)
            elif st == 2: correct_s2.append(is_correct)
            else: correct_s3plus.append(is_correct)
            
            if meta_list[idx]['is_bot']:
                correct_bot.append(is_correct)

    acc = np.mean(correct_all) * 100
    z = (acc - 50.0) / math.sqrt(25.0 / len(correct_all))
    acc_s1 = np.mean(correct_s1) * 100
    acc_s2 = np.mean(correct_s2) * 100
    acc_s3 = np.mean(correct_s3plus) * 100
    acc_bot = np.mean(correct_bot) * 100
    
    print(f"  Overall Pure Out-of-Sample Accuracy: {acc:.2f}% (z = {z:+.2f})")
    print(f"  Streak == 1 Accuracy (Singles):       {acc_s1:.2f}% (N={len(correct_s1)})")
    print(f"  Streak == 2 Accuracy (Pairs):         {acc_s2:.2f}% (N={len(correct_s2)})")
    print(f"  Streak >= 3 Accuracy (Deep Streaks):  {acc_s3:.2f}% (N={len(correct_s3plus)})")
    print(f"  Bot Sessions Out-of-Sample Accuracy:  {acc_bot:.2f}% (N={len(correct_bot)})")
