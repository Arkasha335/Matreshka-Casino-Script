"""
Deep Research & Architecture Search for v16.0 APEX-Neural Engine.
Tests multiple feature sets, neural topologies, and gating thresholds across all 48 real sessions.
Strict Leave-One-Session-Out Cross-Validation (48 folds).
"""
import glob, json, math, os, sys
import numpy as np
from collections import defaultdict
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_2

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

def extract_advanced_features(sessions):
    """
    Extracts 36 causal features:
    - 8 raw recent outcomes (+1/-1/0)
    - 5 alternation frequencies (w=4, 6, 8, 12, 16)
    - 3 color dominance ratios (w=8, 16, 24)
    - 4 streak descriptors (signed, abs, is_pair, is_streak3, is_deep)
    - 3 ZERO clustering metrics (z10, z25, spins_since_zero)
    - 3 empirical Bayesian session transition trackers (pair_cont, s3_break, alt_diff)
    - 4 harmonic / cyclic autocovariance features (lag2, lag3, lag4, lag5 same-color indicator)
    - 3 session macro-statistics (session_red_ratio, session_alt_ratio, total_spins_seen)
    - 2 volatility / entropy indicators (shannon entropy of last 12 spins, run length variance)
    """
    X_list = []
    y_list = []
    sess_ids = []
    meta_list = []

    for s_idx, sess in enumerate(sessions):
        outs = sess['outcomes']
        hist = []

        pair_cont, pair_break = 1, 1
        s3_cont, s3_break = 1, 1
        alt_same, alt_diff = 1, 1

        for t, outcome in enumerate(outs):
            if outcome in ('RED', 'BLACK') and len(hist) >= 4:
                nz = [h for h in hist if h != 'ZERO']
                if len(nz) >= 3:
                    feats = []

                    # 1. Recent raw outcomes (last 8 non-zero spins)
                    for k in range(1, 9):
                        if len(nz) >= k: feats.append(1.0 if nz[-k] == 'RED' else -1.0)
                        else: feats.append(0.0)

                    # 2. Alternation frequencies
                    for w in [4, 6, 8, 12, 16]:
                        sub = nz[-w:]
                        if len(sub) >= 2:
                            trans = sum(1 for i in range(1, len(sub)) if sub[i] != sub[i-1])
                            feats.append(trans / (len(sub) - 1))
                        else: feats.append(0.5)

                    # 3. Color dominance ratios
                    for w in [8, 16, 24]:
                        sub = nz[-w:]
                        if sub: feats.append(sum(1 for x in sub if x == 'RED') / len(sub))
                        else: feats.append(0.5)

                    # 4. Streak descriptors
                    cur_color = nz[-1]
                    streak = 1
                    for k in range(len(nz) - 2, -1, -1):
                        if nz[k] == cur_color: streak += 1
                        else: break
                    signed_streak = streak if cur_color == 'RED' else -streak
                    feats.append(float(signed_streak))
                    feats.append(float(streak))
                    feats.append(1.0 if streak == 2 else 0.0) # pair
                    feats.append(1.0 if streak == 3 else 0.0) # streak 3
                    feats.append(1.0 if streak >= 4 else 0.0) # deep streak

                    # 5. ZERO clustering
                    z10 = sum(1 for x in hist[-10:] if x == 'ZERO')
                    z25 = sum(1 for x in hist[-25:] if x == 'ZERO')
                    feats.append(float(z10))
                    feats.append(float(z25))
                    spins_since_zero = 0
                    for k in range(len(hist) - 1, -1, -1):
                        if hist[k] == 'ZERO': break
                        spins_since_zero += 1
                    feats.append(float(min(spins_since_zero, 30)))

                    # 6. Empirical Bayesian session transition trackers
                    feats.append(pair_cont / (pair_cont + pair_break))
                    feats.append(s3_break / (s3_cont + s3_break))
                    feats.append(alt_diff / (alt_same + alt_diff))

                    # 7. Harmonic autocovariance features (lag 2, 3, 4, 5)
                    for lag in [2, 3, 4, 5]:
                        if len(nz) >= lag + 1:
                            feats.append(1.0 if nz[-1] == nz[-(lag+1)] else -1.0)
                        else: feats.append(0.0)

                    # 8. Session macro-statistics
                    reds_seen = sum(1 for x in nz if x == 'RED')
                    feats.append(reds_seen / len(nz))
                    total_trans = sum(1 for i in range(1, len(nz)) if nz[i] != nz[i-1])
                    feats.append(total_trans / (len(nz) - 1) if len(nz) > 1 else 0.5)
                    feats.append(float(min(len(hist) / 500.0, 2.0)))

                    # 9. Shannon entropy of last 12 spins
                    sub12 = nz[-12:]
                    if sub12:
                        p_r = sum(1 for x in sub12 if x == 'RED') / len(sub12)
                        p_b = 1.0 - p_r
                        ent = 0.0
                        if p_r > 0: ent -= p_r * math.log2(p_r)
                        if p_b > 0: ent -= p_b * math.log2(p_b)
                        feats.append(ent)
                    else: feats.append(1.0)

                    X_list.append(feats)
                    y_list.append(1 if outcome == 'RED' else 0)
                    sess_ids.append(s_idx)
                    meta_list.append({
                        'sess_name': sess['file'],
                        'hist_copy': list(hist),
                        'outcome': outcome,
                        'is_bot': sess['source'] == 'bot_log'
                    })

            # Update session transition counters
            hist.append(outcome)
            nz_cur = [h for h in hist if h != 'ZERO']
            if len(nz_cur) >= 3:
                prev_s, prev_c = 1, nz_cur[-2]
                for i in range(len(nz_cur) - 3, -1, -1):
                    if nz_cur[i] == prev_c: prev_s += 1
                    else: break
                actual = nz_cur[-1]
                if prev_s == 2 and (len(nz_cur) < 4 or nz_cur[-4] != prev_c):
                    if actual == prev_c: pair_cont += 1
                    else: pair_break += 1
                elif prev_s >= 3:
                    if actual == prev_c: s3_cont += 1
                    else: s3_break += 1
                elif prev_s == 1:
                    if actual == prev_c: alt_same += 1
                    else: alt_diff += 1

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32), np.array(sess_ids), meta_list

if __name__ == '__main__':
    X, y, sess_ids, meta = extract_advanced_features(sessions)
    print(f"Dataset shape: {X.shape} across {len(np.unique(sess_ids))} sessions.")

    # Test neural architectures in 48-fold LOSO CV
    archs = [
        ('MLP_24_12_tanh_a0.1', (24, 12), 'tanh', 0.1),
        ('MLP_32_16_tanh_a0.05', (32, 16), 'tanh', 0.05),
        ('MLP_16_8_tanh_a0.1', (16, 8), 'tanh', 0.1),
        ('MLP_24_12_relu_a0.1', (24, 12), 'relu', 0.1),
    ]

    unique_sessions = np.unique(sess_ids)

    for name, hidden, act, alpha in archs:
        print(f"\nEvaluating {name}...")
        preds_all = []
        gated_preds = []
        conf_list = []

        for s_idx in unique_sessions:
            tr = (sess_ids != s_idx)
            te = (sess_ids == s_idx)

            sc = StandardScaler()
            X_tr = sc.fit_transform(X[tr])
            X_te = sc.transform(X[te])

            clf = MLPClassifier(hidden_layer_sizes=hidden, activation=act, alpha=alpha, max_iter=200, random_state=42)
            clf.fit(X_tr, y[tr])
            probs = clf.predict_proba(X_te)[:, 1]

            preds_all.extend((probs >= 0.5).astype(int) == y[te])

            # Gated with v15.2
            test_indices = np.where(te)[0]
            for i, idx in enumerate(test_indices):
                p = probs[i]
                conf = abs(p - 0.5)
                conf_list.append(conf)
                if conf >= 0.08:
                    pred = 1 if p >= 0.5 else 0
                else:
                    p_v15_2 = 1 if predict_v15_2(meta[idx]['hist_copy']) == 'RED' else 0
                    pred = p_v15_2
                gated_preds.append(pred == y[te][i])

        pure_acc = np.mean(preds_all) * 100
        gated_acc = np.mean(gated_preds) * 100
        z_pure = (pure_acc - 50.0) / math.sqrt(25.0 / len(preds_all))
        z_gated = (gated_acc - 50.0) / math.sqrt(25.0 / len(gated_preds))

        # Bot subset
        bot_mask = np.array([m['is_bot'] for m in meta])
        bot_gated = np.mean(np.array(gated_preds)[bot_mask]) * 100

        print(f"  -> Pure Out-of-Sample:  {pure_acc:.2f}% (z={z_pure:+.2f})")
        print(f"  -> Gated Out-of-Sample: {gated_acc:.2f}% (z={z_gated:+.2f}) | Bot WR: {bot_gated:.2f}%")

