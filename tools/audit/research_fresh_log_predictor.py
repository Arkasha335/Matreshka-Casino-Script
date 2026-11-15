import json
import sys
sys.path.insert(0, 'tools/audit')
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror, GAME_RULES, js_round
from parity_ts_vs_python import predict_v15, predict_v13

log_path = 'bot/logs/session_20261115_200052.jsonl'
lines = [json.loads(l) for l in open(log_path, encoding='utf-8') if l.strip()]
outcomes = [r['outcome'] for r in lines]

print(f"Loaded {len(outcomes)} spins from fresh log.")

# Test 1: Baseline v15 predictor accuracy
hist = []
correct_v15 = 0
correct_v13 = 0
evaluated = 0

for o in outcomes:
    if len(hist) >= 5:
        evaluated += 1
        p15 = predict_v15(hist, window=24)
        p13 = predict_v13(hist, window=15)
        if o == p15 and o != 'ZERO':
            correct_v15 += 1
        if o == p13 and o != 'ZERO':
            correct_v13 += 1
    hist.append(o)

print(f"Evaluated spins: {evaluated}")
print(f"v15 Predictor (W=24, Sat-Aware, Deep-Fade): Wins={correct_v15} ({correct_v15/evaluated*100:.2f}%)")
print(f"v13 Predictor (W=15): Wins={correct_v13} ({correct_v13/evaluated*100:.2f}%)")

# Let's test different rolling window sizes for Alpha/Half-wheel skew on this log
for w in [8, 12, 16, 20, 24, 28, 32, 40]:
    hist = []
    wins = 0
    for o in outcomes:
        if len(hist) >= 5:
            p = predict_v15(hist, window=w)
            if o == p and o != 'ZERO':
                wins += 1
        hist.append(o)
    print(f"  Window {w:2d}: Wins={wins} ({wins/evaluated*100:.2f}%)")
