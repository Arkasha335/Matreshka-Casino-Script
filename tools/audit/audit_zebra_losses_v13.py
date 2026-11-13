import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_v14_deep_audit import load_all_29
from research_v14_exact_ts_rules import predict_ts_v13_with_rule

sessions = load_all_29()

zebra_v13_wins = []
zebra_v13_losses = []
zebra_v13_rules = {}

for fn, outs in sessions:
    hist = []
    for o in outs:
        if not hist:
            hist.append(o)
            continue
        raw_m = PrngDetectorMirror.detect_mode(hist)
        z10 = sum(1 for x in hist[-10:] if x == "ZERO")
        mode = "TRANSITION" if (z10 >= 3 and raw_m == "ZEBRA") else raw_m
        rec, conf, state = predict_ts_v13_with_rule(hist)

        if mode == "ZEBRA":
            st = zebra_v13_rules.setdefault(state, [0, 0])
            if o == rec and o != "ZERO":
                st[0] += 1
                zebra_v13_wins.append((fn, state, o))
            elif o != "ZERO":
                st[1] += 1
                zebra_v13_losses.append((fn, state, o))
        hist.append(o)

tot_w = len(zebra_v13_wins)
tot_l = len(zebra_v13_losses)
tot = tot_w + tot_l
print(
    f"=== EXACT TS v13.0 IN ZEBRA MODE: Wins={tot_w}, Losses={tot_l}, Total={tot} ==="
)
print(f"Non-Zero Win Rate: {tot_w/tot*100:.2f}%\n")
print(
    f"{'Rule Name':30s} | {'Wins':5s} | {'Losses':6s} | {'Total':5s} | {'Win Rate':8s}"
)
print("-" * 65)
for r, (w, l) in sorted(
    zebra_v13_rules.items(), key=lambda x: -(x[1][0] + x[1][1])
):
    t = w + l
    print(f"{r:30s} | {w:5d} | {l:6d} | {t:5d} | {w/t*100:6.2f}%")
