"""
Diagnose v16.0 Neural Weights and Feature Sensitivity on Spins 326-331.
"""
import json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from engine_mirror import PrngDetectorMirror, NEURAL_WEIGHTS_V16

path = 'bot/logs/session_20261117_165453.jsonl'
lines = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]

hist = [l['outcome'] for l in lines]

w1 = np.array(NEURAL_WEIGHTS_V16['weights']['w1'])
b1 = np.array(NEURAL_WEIGHTS_V16['weights']['b1'])
w2 = np.array(NEURAL_WEIGHTS_V16['weights']['w2'])
b2 = np.array(NEURAL_WEIGHTS_V16['weights']['b2'])
w3 = np.array(NEURAL_WEIGHTS_V16['weights']['w3'])
b3 = NEURAL_WEIGHTS_V16['weights']['b3'][0]
mu = np.array(NEURAL_WEIGHTS_V16['scaler']['mean'])
scale = np.array(NEURAL_WEIGHTS_V16['scaler']['scale'])

feature_names = [
    "raw_lag1", "raw_lag2", "raw_lag3", "raw_lag4", "raw_lag5", "raw_lag6", "raw_lag7", "raw_lag8",
    "signed_streak", "streak", "streak_eq1", "streak_eq2", "streak_eq3", "streak_gte4",
    "alt_w4", "alt_w6", "alt_w8", "alt_w12", "alt_w16",
    "red_ratio_w8", "red_ratio_w16", "red_ratio_w24",
    "zero_w10", "zero_w25", "spins_since_zero",
    "pair_cont_rate", "s3_break_rate", "alt_diff_rate",
    "micro_aba", "micro_aab"
]

print("Analyzing Feature Contributions for spins 326-331:")
for target_spin in range(326, 332):
    sub_hist = hist[:target_spin-1]
    feats = PrngDetectorMirror.extract_features(sub_hist)
    z = (np.array(feats) - mu) / scale
    
    # Layer 1
    h1 = np.tanh(z @ w1 + b1)
    # Layer 2
    h2 = np.tanh(h1 @ w2 + b2)
    # Output
    out_val = h2 @ w3 + b3
    p_red = 1.0 / (1.0 + np.exp(-out_val[0]))
    
    # Linear approximation of feature gradient / sensitivity: d(out_val)/dz
    # dh2/dh1 = diag(1 - h2^2) @ w2^T
    # dh1/dz = diag(1 - h1^2) @ w1^T
    # dout/dz = w3^T @ diag(1 - h2^2) @ w2^T @ diag(1 - h1^2) @ w1^T
    grad_h2 = (1 - h2**2) * w3[:, 0]
    grad_h1 = (grad_h2 @ w2.T) * (1 - h1**2)
    grad_z = grad_h1 @ w1.T
    
    top_pos_features = np.argsort(grad_z * z)[-5:][::-1]
    top_neg_features = np.argsort(grad_z * z)[:5]
    
    cur_streak = feats[9]
    last_col = "RED" if feats[8] > 0 else "BLACK"
    
    print(f"\nSpin #{target_spin} | Out: {hist[target_spin-1]} | pRed: {p_red:.4f} | Streak: {cur_streak} {last_col}")
    print("  Top drivers towards RED:")
    for idx in top_pos_features:
        if (grad_z * z)[idx] > 0.05:
            print(f"    {feature_names[idx]:<18}: val={feats[idx]:>6.2f}, z={z[idx]:>+5.2f}, grad={grad_z[idx]:>+5.2f}, impact={grad_z[idx]*z[idx]:>+6.3f}")
    print("  Top drivers towards BLACK:")
    for idx in top_neg_features:
        if (grad_z * z)[idx] < -0.05:
            print(f"    {feature_names[idx]:<18}: val={feats[idx]:>6.2f}, z={z[idx]:>+5.2f}, grad={grad_z[idx]:>+5.2f}, impact={grad_z[idx]*z[idx]:>+6.3f}")
