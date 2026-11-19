"""
Analyze why MLP v16.0 consistently predicts SWITCH on streak=1 and CONTINUE on streak=2.
"""
import json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from engine_mirror import NEURAL_WEIGHTS_V16

w1 = np.array(NEURAL_WEIGHTS_V16['weights']['w1'])
b1 = np.array(NEURAL_WEIGHTS_V16['weights']['b1'])
w2 = np.array(NEURAL_WEIGHTS_V16['weights']['w2'])
b2 = np.array(NEURAL_WEIGHTS_V16['weights']['b2'])
w3 = np.array(NEURAL_WEIGHTS_V16['weights']['w3'])
b3 = NEURAL_WEIGHTS_V16['weights']['b3'][0]
mu = np.array(NEURAL_WEIGHTS_V16['scaler']['mean'])
scale = np.array(NEURAL_WEIGHTS_V16['scaler']['scale'])

# Let's test synthetic feature vectors where:
# Case A: streak = 1 RED, all other features neutral (0.5 or 0)
# Case B: streak = 2 RED, all other features neutral
# Case C: streak = 1 BLACK, all other features neutral
# Case D: streak = 2 BLACK, all other features neutral

def forward(feats):
    z = (np.array(feats) - mu) / scale
    h1 = np.tanh(z @ w1 + b1)
    h2 = np.tanh(h1 @ w2 + b2)
    out = h2 @ w3 + b3
    return 1.0 / (1.0 + np.exp(-out[0]))

base_feats = [0.0]*30
base_feats[14:19] = [0.5]*5 # alts
base_feats[19:22] = [0.5]*3 # red ratios
base_feats[25] = 0.5 # pair_cont
base_feats[26] = 0.5 # s3_break
base_feats[27] = 0.5 # alt_diff

# 1. Streak = 1 RED (last color was RED)
f_s1_red = list(base_feats)
f_s1_red[0] = 1.0 # lag1 = RED
f_s1_red[8] = 1.0 # signed_streak = +1
f_s1_red[9] = 1.0 # streak = 1
f_s1_red[10] = 1.0 # streak_eq1 = 1
p_s1_r = forward(f_s1_red)

# 2. Streak = 2 RED (last 2 were RED)
f_s2_red = list(base_feats)
f_s2_red[0] = 1.0 # lag1 = RED
f_s2_red[1] = 1.0 # lag2 = RED
f_s2_red[8] = 2.0 # signed_streak = +2
f_s2_red[9] = 2.0 # streak = 2
f_s2_red[11] = 1.0 # streak_eq2 = 1
p_s2_r = forward(f_s2_red)

# 3. Streak = 1 BLACK (last color was BLACK)
f_s1_blk = list(base_feats)
f_s1_blk[0] = -1.0 # lag1 = BLACK
f_s1_blk[8] = -1.0 # signed_streak = -1
f_s1_blk[9] = 1.0 # streak = 1
f_s1_blk[10] = 1.0 # streak_eq1 = 1
p_s1_b = forward(f_s1_blk)

# 4. Streak = 2 BLACK (last 2 were BLACK)
f_s2_blk = list(base_feats)
f_s2_blk[0] = -1.0 # lag1 = BLACK
f_s2_blk[1] = -1.0 # lag2 = BLACK
f_s2_blk[8] = -2.0 # signed_streak = -2
f_s2_blk[9] = 2.0 # streak = 2
f_s2_blk[11] = 1.0 # streak_eq2 = 1
p_s2_b = forward(f_s2_blk)

print(f"Synthetic Baseline Predictions:")
print(f"  Streak = 1 RED:   pRed = {p_s1_r:.4f} -> Predicts {'RED (REPEAT)' if p_s1_r > 0.5 else 'BLACK (SWITCH)'}")
print(f"  Streak = 2 RED:   pRed = {p_s2_r:.4f} -> Predicts {'RED (CONTINUE 3)' if p_s2_r > 0.5 else 'BLACK (BREAK PAIR)'}")
print(f"  Streak = 1 BLACK: pRed = {p_s1_b:.4f} -> Predicts {'RED (SWITCH)' if p_s1_b > 0.5 else 'BLACK (REPEAT)'}")
print(f"  Streak = 2 BLACK: pRed = {p_s2_b:.4f} -> Predicts {'RED (BREAK PAIR)' if p_s2_b > 0.5 else 'BLACK (CONTINUE 3)'}")
