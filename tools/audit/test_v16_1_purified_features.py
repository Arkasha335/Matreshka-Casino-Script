"""
Test feature ablation: What happens to out-of-sample accuracy when removing
spurious features (spins_since_zero, raw_lag4..8) and replacing them with
causal streak-mood features?
"""
import glob, json, math, os, sys
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()

def extract_features_v16_original(hist):
    nz = [x for x in hist if x != 'ZERO']
    if len(nz) < 3 or len(hist) < 4: return None
    feats = []
    # 8 lags
    for k in range(1, 9):
        if len(nz) >= k: feats.append(1.0 if nz[-k] == 'RED' else -1.0)
        else: feats.append(0.0)
    cur_c = nz[-1]
    s = 1
    for k in range(len(nz)-2, -1, -1):
        if nz[k] == cur_c: s += 1
        else: break
    signed_s = s if cur_c == 'RED' else -s
    feats.extend([float(signed_s), float(s), 1.0 if s==1 else 0.0, 1.0 if s==2 else 0.0, 1.0 if s==3 else 0.0, 1.0 if s>=4 else 0.0])
    for w in [4, 6, 8, 12, 16]:
        sub = nz[-w:]
        if len(sub) >= 2:
            t = sum(1 for j in range(1, len(sub)) if sub[j] != sub[j-1])
            feats.append(t / (len(sub) - 1))
        else: feats.append(0.5)
    for w in [8, 16, 24]:
        sub = nz[-w:]
        feats.append(sum(1 for x in sub if x == 'RED') / len(sub) if sub else 0.5)
    z10 = sum(1 for x in hist[-10:] if x == 'ZERO')
    z25 = sum(1 for x in hist[-25:] if x == 'ZERO')
    feats.extend([float(z10), float(z25)])
    spins_since_zero = 0
    for k in range(len(hist)-1, -1, -1):
        if hist[k] == 'ZERO': break
        spins_since_zero += 1
    feats.append(float(min(spins_since_zero, 30)))
    pair_cont, pair_break, s3_cont, s3_break, alt_same, alt_diff = 1, 1, 1, 1, 1, 1
    for i in range(2, len(nz)):
        ps, pc = 1, nz[i-1]
        for j in range(i-2, -1, -1):
            if nz[j] == pc: ps += 1
            else: break
        act = nz[i]
        if ps == 2 and (i < 3 or nz[i-3] != pc):
            if act == pc: pair_cont += 1
            else: pair_break += 1
        elif ps >= 3:
            if act == pc: s3_cont += 1
            else: s3_break += 1
        elif ps == 1:
            if act == nz[i-1]: alt_same += 1
            else: alt_diff += 1
    feats.extend([pair_cont/(pair_cont+pair_break), s3_break/(s3_cont+s3_break), alt_diff/(alt_same+alt_diff)])
    feats.append(1.0 if (len(nz)>=3 and nz[-1]==nz[-3] and nz[-1]!=nz[-2]) else 0.0)
    feats.append(1.0 if (len(nz)>=3 and nz[-2]==nz[-3] and nz[-1]!=nz[-2]) else 0.0)
    return feats

def extract_features_v16_1_purified(hist):
    nz = [x for x in hist if x != 'ZERO']
    if len(nz) < 3 or len(hist) < 4: return None
    feats = []
    
    # 1. Recent raw outcomes: ONLY LAG 1, 2, 3 (Immediate micro-memory)
    for k in range(1, 4):
        if len(nz) >= k: feats.append(1.0 if nz[-k] == 'RED' else -1.0)
        else: feats.append(0.0)
        
    cur_c = nz[-1]
    opp_c = 'BLACK' if cur_c == 'RED' else 'RED'
    s = 1
    for k in range(len(nz)-2, -1, -1):
        if nz[k] == cur_c: s += 1
        else: break
    signed_s = s if cur_c == 'RED' else -s
    feats.extend([
        float(signed_s), float(s),
        1.0 if s == 1 else 0.0,
        1.0 if s == 2 else 0.0,
        1.0 if s == 3 else 0.0,
        1.0 if s >= 4 else 0.0
    ])
    
    # 2. Previous opposite streak length (Memory of last completed streak)
    prev_s = 1
    idx_prev = len(nz) - 1 - s
    if idx_prev >= 0:
        for k in range(idx_prev - 1, -1, -1):
            if nz[k] == opp_c: prev_s += 1
            else: break
    feats.append(float(min(prev_s, 6)))
    feats.append(1.0 if prev_s == 1 else 0.0)
    feats.append(1.0 if prev_s == 2 else 0.0)
    feats.append(1.0 if prev_s >= 3 else 0.0)
    
    # 3. Rolling average streak length per color (Window 24)
    w24 = nz[-24:]
    st_r, st_b = [], []
    if w24:
        tc = w24[0]; tl = 1
        for j in range(1, len(w24)):
            if w24[j] == tc: tl += 1
            else:
                if tc == 'RED': st_r.append(tl)
                else: st_b.append(tl)
                tc = w24[j]; tl = 1
        if tc == 'RED': st_r.append(tl)
        else: st_b.append(tl)
    avg_r = sum(st_r) / len(st_r) if st_r else 1.8
    avg_b = sum(st_b) / len(st_b) if st_b else 1.8
    feats.append(avg_r)
    feats.append(avg_b)
    feats.append(avg_r - avg_b) # Color streak asymmetry
    
    # Relative streak exhaustion (current streak / avg streak of this color)
    avg_cur = avg_r if cur_c == 'RED' else avg_b
    feats.append(float(s) / max(1.0, avg_cur))
    
    # 4. Alternation rates
    for w in [4, 6, 8, 12, 16]:
        sub = nz[-w:]
        if len(sub) >= 2:
            t = sum(1 for j in range(1, len(sub)) if sub[j] != sub[j-1])
            feats.append(t / (len(sub) - 1))
        else: feats.append(0.5)
        
    # 5. Color ratios (Dominance)
    for w in [8, 16, 24]:
        sub = nz[-w:]
        feats.append(sum(1 for x in sub if x == 'RED') / len(sub) if sub else 0.5)
        
    # 6. Empirical Bayesian session counters
    pair_cont, pair_break, s3_cont, s3_break, alt_same, alt_diff = 1, 1, 1, 1, 1, 1
    for i in range(2, len(nz)):
        ps, pc = 1, nz[i-1]
        for j in range(i-2, -1, -1):
            if nz[j] == pc: ps += 1
            else: break
        act = nz[i]
        if ps == 2 and (i < 3 or nz[i-3] != pc):
            if act == pc: pair_cont += 1
            else: pair_break += 1
        elif ps >= 3:
            if act == pc: s3_cont += 1
            else: s3_break += 1
        elif ps == 1:
            if act == nz[i-1]: alt_same += 1
            else: alt_diff += 1
    feats.extend([pair_cont/(pair_cont+pair_break), s3_break/(s3_cont+s3_break), alt_diff/(alt_same+alt_diff)])
    
    # 7. Micro-patterns (A-B-A and A-A-B)
    feats.append(1.0 if (len(nz)>=3 and nz[-1]==nz[-3] and nz[-1]!=nz[-2]) else 0.0)
    feats.append(1.0 if (len(nz)>=3 and nz[-2]==nz[-3] and nz[-1]!=nz[-2]) else 0.0)
    
    return feats

if __name__ == '__main__':
    print("Building datasets for v16.0 Original vs v16.1 Purified...")
    X_v16_list, X_v16_1_list, y_list, sess_ids, meta = [], [], [], [], []

    for s_idx, sess in enumerate(sessions):
        outs = sess['outcomes']
        hist = []
        for t, out in enumerate(outs):
            if out in ('RED', 'BLACK') and len(hist) >= 4:
                nz = [h for h in hist if h != 'ZERO']
                if len(nz) >= 3:
                    f0 = extract_features_v16_original(hist)
                    f1 = extract_features_v16_1_purified(hist)
                    if f0 and f1:
                        X_v16_list.append(f0)
                        X_v16_1_list.append(f1)
                        y_list.append(1 if out == 'RED' else 0)
                        sess_ids.append(s_idx)
                        meta.append({'sess': sess['file'], 'is_bot': sess['source'] == 'bot_log', 'is_fresh': '20261117' in sess['file']})
            hist.append(out)

    X0 = np.array(X_v16_list, dtype=np.float32)
    X1 = np.array(X_v16_1_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    sess_ids = np.array(sess_ids)

    print(f"X0 (v16.0 original): {X0.shape[1]} features.")
    print(f"X1 (v16.1 purified): {X1.shape[1]} features.")

    # Evaluate in 49-fold LOSO CV
    unique_sessions = np.unique(sess_ids)

    for name, X_data in [('v16.0 Original (30 feats)', X0), ('v16.1 Purified + Streak Mood (29 feats)', X1)]:
        preds_all = []
        preds_fresh = []
        preds_bot = []
        
        for s_idx in unique_sessions:
            tr = (sess_ids != s_idx)
            te = (sess_ids == s_idx)
            
            sc = StandardScaler()
            X_tr = sc.fit_transform(X_data[tr])
            X_te = sc.transform(X_data[te])
            
            clf = MLPClassifier(hidden_layer_sizes=(24, 12), activation='tanh', alpha=0.1, max_iter=200, random_state=42)
            clf.fit(X_tr, y[tr])
            probs = clf.predict_proba(X_te)[:, 1]
            
            test_indices = np.where(te)[0]
            for i, idx in enumerate(test_indices):
                p = probs[i]
                pred = 1 if p >= 0.5 else 0
                is_correct = (pred == y[te][i])
                preds_all.append(is_correct)
                if meta[idx]['is_fresh']: preds_fresh.append(is_correct)
                if meta[idx]['is_bot']: preds_bot.append(is_correct)
                
        acc_all = np.mean(preds_all) * 100
        acc_fresh = np.mean(preds_fresh) * 100
        acc_bot = np.mean(preds_bot) * 100
        z = (acc_all - 50.0) / math.sqrt(25.0 / len(preds_all))
        
        print(f"\n{name}:")
        print(f"  All 49 Sessions Pure Accuracy: {acc_all:.2f}% (z = {z:+.2f})")
        print(f"  All Bot Sessions Pure Accuracy: {acc_bot:.2f}% (N = {len(preds_bot)})")
        print(f"  FRESH SESSION (17.11) Accuracy: {acc_fresh:.2f}% (N = {len(preds_fresh)})")

