"""
Neural Network & ML Research for v16.0 Engine.
Strict Leave-One-Session-Out Cross-Validation (LOSO-CV) across all 48 sessions.
Zero data leakage: Model trains on N-1 sessions and evaluates on held-out session.
"""
import glob, json, math, os, sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_1, predict_v15_2

from sklearn.neural_network import MLPClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

def extract_features_and_labels(sessions):
    """
    Extracts time-series features and labels for each bettable spin (where outcome is RED or BLACK).
    Zero data leakage: only uses past spins up to t-1 to predict spin t.
    """
    X_list = []
    y_list = []
    session_ids = []
    meta_list = []

    for s_idx, sess in enumerate(sessions):
        outs = sess['outcomes']
        hist = []

        # Session-level running accumulators
        pair_cont = 1
        pair_break = 1
        s3_cont = 1
        s3_break = 1
        alt_same = 1
        alt_diff = 1

        for t, outcome in enumerate(outs):
            # Only train/predict on non-zero outcomes as target y (RED=1, BLACK=0)
            if outcome in ('RED', 'BLACK') and len(hist) >= 4:
                nz = [h for h in hist if h != 'ZERO']
                if len(nz) >= 3:
                    # Feature Extraction at time t (strictly causal)
                    feats = []

                    # 1. Recent raw outcomes (last 8 non-zero spins: RED=+1, BLACK=-1)
                    for k in range(1, 9):
                        if len(nz) >= k:
                            feats.append(1.0 if nz[-k] == 'RED' else -1.0)
                        else:
                            feats.append(0.0)

                    # 2. Streak features
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

                    # 3. Alternation rates at windows 4, 6, 8, 12, 16
                    for w in [4, 6, 8, 12, 16]:
                        sub = nz[-w:]
                        if len(sub) >= 2:
                            trans = sum(1 for i in range(1, len(sub)) if sub[i] != sub[i-1])
                            feats.append(trans / (len(sub) - 1))
                        else:
                            feats.append(0.5)

                    # 4. Color ratios at windows 8, 16, 24
                    for w in [8, 16, 24]:
                        sub = nz[-w:]
                        if sub:
                            rc = sum(1 for x in sub if x == 'RED')
                            feats.append(rc / len(sub))
                        else:
                            feats.append(0.5)

                    # 5. ZERO features in recent history
                    z10 = sum(1 for x in hist[-10:] if x == 'ZERO')
                    z25 = sum(1 for x in hist[-25:] if x == 'ZERO')
                    feats.append(float(z10))
                    feats.append(float(z25))

                    spins_since_zero = 0
                    for k in range(len(hist) - 1, -1, -1):
                        if hist[k] == 'ZERO': break
                        spins_since_zero += 1
                    feats.append(float(min(spins_since_zero, 30)))

                    # 6. Empirical Bayesian session counters
                    p_cont_rate = pair_cont / (pair_cont + pair_break)
                    s3_brk_rate = s3_break / (s3_cont + s3_break)
                    alt_diff_rate = alt_diff / (alt_same + alt_diff)
                    feats.append(p_cont_rate)
                    feats.append(s3_brk_rate)
                    feats.append(alt_diff_rate)

                    # 7. Micro-patterns (A-B-A and A-A-B)
                    feats.append(1.0 if (len(nz) >= 3 and nz[-1] == nz[-3] and nz[-1] != nz[-2]) else 0.0)
                    feats.append(1.0 if (len(nz) >= 3 and nz[-2] == nz[-3] and nz[-1] != nz[-2]) else 0.0)

                    X_list.append(feats)
                    y_list.append(1 if outcome == 'RED' else 0)
                    session_ids.append(s_idx)
                    meta_list.append({
                        'sess_name': sess['file'],
                        'hist_copy': list(hist),
                        'outcome': outcome,
                        'is_bot': sess['source'] == 'bot_log'
                    })

            # Update running session counters AFTER spin t is completed
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

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32), np.array(session_ids), meta_list

def run_loso_evaluation():
    sessions = load_all_unique_sessions()
    print(f"Loaded {len(sessions)} unique sessions.")
    X, y, sess_ids, meta = extract_features_and_labels(sessions)
    print(f"Extracted {X.shape[0]} samples with {X.shape[1]} features across {len(np.unique(sess_ids))} sessions.")

    # 1. Evaluate Rule-based Baselines on the exact same dataset
    v15_1_preds = []
    v15_2_preds = []
    for m in meta:
        p1 = predict_v15_1(m['hist_copy'])
        p2 = predict_v15_2(m['hist_copy'])
        v15_1_preds.append(1 if p1 == 'RED' else 0)
        v15_2_preds.append(1 if p2 == 'RED' else 0)

    v15_1_acc = np.mean(np.array(v15_1_preds) == y) * 100
    v15_2_acc = np.mean(np.array(v15_2_preds) == y) * 100

    print("\n" + "="*85)
    print(" BASELINE MODELS ACCURACY (Non-Zero Spins):")
    print("="*85)
    print(f"  v15.0 / v15.1 (Rule-based MPD):             {v15_1_acc:.2f}% ({(v15_1_acc-50)/math.sqrt(25/len(y)):+.2f} sigma)")
    print(f"  v15.2 (Synthesized Optimal):                {v15_2_acc:.2f}% ({(v15_2_acc-50)/math.sqrt(25/len(y)):+.2f} sigma)")

    # 2. Leave-One-Session-Out Cross Validation for ML & Neural Models
    unique_sessions = np.unique(sess_ids)

    models = {
        'Logistic Regression (L2)': lambda: LogisticRegression(C=0.1, max_iter=200, random_state=42),
        'APEX-MLP (32-16 Neural Net)': lambda: MLPClassifier(hidden_layer_sizes=(32, 16), activation='tanh', alpha=0.05, max_iter=150, random_state=42, early_stopping=False),
        'Gradient Boosting (n=50, d=2)': lambda: GradientBoostingClassifier(n_estimators=50, max_depth=2, learning_rate=0.05, random_state=42),
        'Hybrid Neuro-Symbolic (Ensemble)': None # Will blend MLP + v15.2
    }

    results = defaultdict(list)
    confidences = defaultdict(list)

    print("\nRunning Leave-One-Session-Out Cross Validation (48 folds)...")
    for s_idx in unique_sessions:
        train_mask = (sess_ids != s_idx)
        test_mask = (sess_ids == s_idx)

        X_train, y_train = X[train_mask], y[train_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train models
        mlp = MLPClassifier(hidden_layer_sizes=(32, 16), activation='tanh', alpha=0.05, max_iter=150, random_state=42)
        mlp.fit(X_train_scaled, y_train)
        mlp_probs = mlp.predict_proba(X_test_scaled)[:, 1]
        mlp_preds = (mlp_probs >= 0.5).astype(int)
        results['APEX-MLP (32-16 Neural Net)'].extend(mlp_preds == y_test)
        confidences['APEX-MLP (32-16 Neural Net)'].extend(np.abs(mlp_probs - 0.5) * 200)

        lr = LogisticRegression(C=0.1, max_iter=200, random_state=42)
        lr.fit(X_train_scaled, y_train)
        lr_probs = lr.predict_proba(X_test_scaled)[:, 1]
        lr_preds = (lr_probs >= 0.5).astype(int)
        results['Logistic Regression (L2)'].extend(lr_preds == y_test)
        confidences['Logistic Regression (L2)'].extend(np.abs(lr_probs - 0.5) * 200)

        gb = GradientBoostingClassifier(n_estimators=50, max_depth=2, learning_rate=0.05, random_state=42)
        gb.fit(X_train, y_train)
        gb_probs = gb.predict_proba(X_test)[:, 1]
        gb_preds = (gb_probs >= 0.5).astype(int)
        results['Gradient Boosting (n=50, d=2)'].extend(gb_preds == y_test)
        confidences['Gradient Boosting (n=50, d=2)'].extend(np.abs(gb_probs - 0.5) * 200)

        # Hybrid Neuro-Symbolic Model:
        # Blends MLP probability with v15.2 prediction:
        # If MLP confidence >= 10% (|p - 0.5| >= 0.05), trust MLP; otherwise fallback to v15.2!
        test_indices = np.where(test_mask)[0]
        hybrid_preds = []
        for i, idx in enumerate(test_indices):
            mlp_p = mlp_probs[i]
            v15_2_p = v15_2_preds[idx]
            
            # Neural Confidence Gating
            if abs(mlp_p - 0.5) >= 0.06:
                pred = 1 if mlp_p >= 0.5 else 0
            else:
                pred = v15_2_p
            hybrid_preds.append(pred)

        results['Hybrid Neuro-Symbolic (Ensemble)'].extend(np.array(hybrid_preds) == y_test)

    print("\n" + "="*95)
    print(" LEAVE-ONE-SESSION-OUT CROSS-VALIDATION RESULTS (OUT-OF-SAMPLE TEST):")
    print("="*95)
    print(f"{'Model Architecture':<36} {'Win Rate':>10} {'Hits':>8} {'Total':>8} {'z-score':>10}")
    print("-" * 95)
    print(f"{'v15.0 / v15.1 Baseline (Rule MPD)':<36} {v15_1_acc:>9.2f}% {sum(np.array(v15_1_preds) == y):>8d} {len(y):>8d} {(v15_1_acc-50)/math.sqrt(25/len(y)):>+10.2f}")
    print(f"{'v15.2 Synthesized Optimal':<36} {v15_2_acc:>9.2f}% {sum(np.array(v15_2_preds) == y):>8d} {len(y):>8d} {(v15_2_acc-50)/math.sqrt(25/len(y)):>+10.2f}")

    for m_name in results:
        res = results[m_name]
        acc = np.mean(res) * 100
        z = (acc - 50.0) / math.sqrt(25.0 / len(res))
        print(f"{m_name:<36} {acc:>9.2f}% {sum(res):>8d} {len(res):>8d} {z:>+10.2f}")

    # Breakdown on Bot Sessions vs Historical
    bot_mask = np.array([m['is_bot'] for m in meta])
    print("\n" + "="*95)
    print(" BREAKDOWN ON REAL BOT SESSIONS (2,799 spins):")
    print("="*95)
    v15_1_bot = np.mean((np.array(v15_1_preds) == y)[bot_mask]) * 100
    v15_2_bot = np.mean((np.array(v15_2_preds) == y)[bot_mask]) * 100
    print(f"  v15.0 / v15.1:                              {v15_1_bot:.2f}%")
    print(f"  v15.2 Synthesized Optimal:                  {v15_2_bot:.2f}%")
    for m_name in results:
        arr = np.array(results[m_name])[bot_mask]
        print(f"  {m_name:<42} {np.mean(arr)*100:.2f}% (z={((np.mean(arr)*100)-50)/math.sqrt(25/len(arr)):+.2f})")

if __name__ == '__main__':
    run_loso_evaluation()
