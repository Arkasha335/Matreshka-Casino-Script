import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_v14_deep_audit import load_all_29
from research_v14_exact_ts_rules import predict_ts_v13_with_rule

sessions = load_all_29()

neutral_cases = []

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

        if mode == "ZEBRA" and state == "НЕЙТРАЛЬНО" and o != "ZERO":
            nz = [h for h in hist if h != "ZERO"]
            L1 = nz[-1] if len(nz) > 0 else None
            L2 = nz[-2] if len(nz) > 1 else None
            L3 = nz[-3] if len(nz) > 2 else None
            L4 = nz[-4] if len(nz) > 3 else None
            L5 = nz[-5] if len(nz) > 4 else None
            is_win = o == rec
            neutral_cases.append((L5, L4, L3, L2, L1, rec, o, is_win))
        hist.append(o)

print(
    f"Total НЕЙТРАЛЬНО cases in ZEBRA: {len(neutral_cases)} (Wins={sum(1 for c in neutral_cases if c[7])}, Losses={sum(1 for c in neutral_cases if not c[7])})"
)

# Look at patterns of L3, L2, L1:
# L1 == L2 by definition of the branch!
# What is L3?
# If L3 == L1: then it's L1=L2=L3 (a 3-streak, e.g. RRR).
# If L3 != L1: then it's a 2-streak (e.g. BRR).
streak3 = [c for c in neutral_cases if c[2] == c[4]]
streak2 = [c for c in neutral_cases if c[2] != c[4]]
print(f"\nWhen L3 == L1 (streak >= 3): {len(streak3)} cases")
print(
    f"When L3 != L1 (exact pair X-Y-Y): {len(streak2)} cases | Wins={sum(1 for c in streak2 if c[7])} ({sum(1 for c in streak2 if c[7])/len(streak2)*100:.1f}%)"
)

# For exact pair X-Y-Y, what was L4?
# If L4 == L3: XXYY (double pair, e.g. BBRR)
# If L4 != L3: XY-YY (alternating into pair, e.g. RBRR)
double_pairs = [c for c in streak2 if c[1] == c[2]]
alt_into_pair = [c for c in streak2 if c[1] != c[2]]
print(
    f"\n  Double pairs (X-X-Y-Y): {len(double_pairs)} | Wins={sum(1 for c in double_pairs if c[7])} ({sum(1 for c in double_pairs if c[7])/len(double_pairs)*100:.1f}%)"
)
print(
    f"  Alternating into pair (X-Y-X-Y-Y): {len(alt_into_pair)} | Wins={sum(1 for c in alt_into_pair if c[7])} ({sum(1 for c in alt_into_pair if c[7])/len(alt_into_pair)*100:.1f}%)"
)
