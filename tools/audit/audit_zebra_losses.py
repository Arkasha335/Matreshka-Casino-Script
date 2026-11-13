import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_v14_deep_audit import load_all_29

sessions = load_all_29()

# Analyze predictor decisions specifically during ZEBRA mode
zebra_losses = []
zebra_wins = []

for fn, outs in sessions:
    hist = []
    for o in outs:
        if not hist:
            hist.append(o)
            continue
        raw_m = PrngDetectorMirror.detect_mode(hist)
        z10 = sum(1 for x in hist[-10:] if x == "ZERO")
        mode = "TRANSITION" if (z10 >= 3 and raw_m == "ZEBRA") else raw_m
        pred_res = PrngDetectorMirror.get_recommendation_and_confidence(hist)
        pred = pred_res[0]
        rule = pred_res[2]

        if mode == "ZEBRA":
            if o == pred and o != "ZERO":
                zebra_wins.append((fn, rule, o))
            elif o != "ZERO":
                nz = [h for h in hist if h != "ZERO"]
                L1 = nz[-1] if nz else None
                L2 = nz[-2] if len(nz) > 1 else None
                L3 = nz[-3] if len(nz) > 2 else None
                zebra_losses.append((fn, rule, pred, o, L1, L2, L3))
        hist.append(o)

print(
    f"=== ZEBRA MODE PERFORMANCE: Wins={len(zebra_wins)}, Losses={len(zebra_losses)} ==="
)
total_z = len(zebra_wins) + len(zebra_losses)
print(
    f"ZEBRA Mode Non-Zero Win Rate: {len(zebra_wins)/total_z*100:.2f}% ({len(zebra_wins)}/{total_z})!"
)

# Rule breakdown in ZEBRA mode:
zebra_rules = {}
for item in zebra_wins:
    r = item[1]
    zebra_rules.setdefault(r, [0, 0])[0] += 1
for item in zebra_losses:
    r = item[1]
    zebra_rules.setdefault(r, [0, 0])[1] += 1

print("\nZEBRA Mode Win Rate by Rule:")
print(
    f"{'Rule Name':30s} | {'Wins':5s} | {'Losses':6s} | {'Total':5s} | {'Win Rate':8s}"
)
print("-" * 65)
for r, (w, l) in sorted(zebra_rules.items(), key=lambda x: -(x[1][0] + x[1][1])):
    tot = w + l
    print(f"{r:30s} | {w:5d} | {l:6d} | {tot:5d} | {w/tot*100:6.2f}%")
