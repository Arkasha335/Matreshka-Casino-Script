import glob
import hashlib
import json
import math
import os
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from parity_ts_vs_python import predict_v13
from research_v14_deep_audit import load_all_29

sessions = load_all_29()

# 1. Analyze conditional streak continuation across all 29 sessions
# Given streak of length L (1, 2, 3, 4, 5, 6, 7, 8), what is P(continue | non-zero)?
streak_cont = {}
streak_break = {}

for _, outs in sessions:
    nz = [o for o in outs if o != "ZERO"]
    cur_len = 1
    for i in range(1, len(nz)):
        prev = nz[i - 1]
        curr = nz[i]
        if curr == prev:
            streak_cont[cur_len] = streak_cont.get(cur_len, 0) + 1
            cur_len += 1
        else:
            streak_break[cur_len] = streak_break.get(cur_len, 0) + 1
            cur_len = 1

print("=== STREAK CONTINUATION VS BREAK PROBABILITIES (All 29 Sessions, 2,575 Non-Zero Spins) ===")
print("Streak Len | Continuations | Breaks | Total | P(Continue) | P(Break) | Theoretical IID")
for L in range(1, 10):
    c = streak_cont.get(L, 0)
    b = streak_break.get(L, 0)
    tot = c + b
    if tot > 0:
        p_c = c / tot * 100
        p_b = b / tot * 100
        print(f"    L={L:2d}   |     {c:4d}      |  {b:4d}  | {tot:5d} |   {p_c:5.2f}%   |  {p_b:5.2f}%  |    50.00%")

# 2. Test Markov Transition Probabilities
# Order 1: P(C_t | C_{t-1})
m1_same = m1_diff = 0
for _, outs in sessions:
    nz = [o for o in outs if o != "ZERO"]
    for i in range(1, len(nz)):
        if nz[i] == nz[i - 1]:
            m1_same += 1
        else:
            m1_diff += 1
print(f"\nOrder 1 (Lag-1): Same={m1_same} ({m1_same/(m1_same+m1_diff)*100:.2f}%), Diff={m1_diff} ({m1_diff/(m1_same+m1_diff)*100:.2f}%)")

# Order 2: P(C_t | C_{t-1}, C_{t-2})
# RR -> R vs B, BB -> B vs R, RB -> R vs B, BR -> B vs R
o2_counts = {}
for _, outs in sessions:
    nz = [o for o in outs if o != "ZERO"]
    for i in range(2, len(nz)):
        pat = f"{nz[i-2][0]}{nz[i-1][0]}"
        nxt = nz[i][0]
        o2_counts.setdefault(pat, {})[nxt] = o2_counts.setdefault(pat, {}).get(nxt, 0) + 1

print("\nOrder 2 Transitions:")
for pat, nxts in sorted(o2_counts.items()):
    tot = sum(nxts.values())
    print(f"  Pattern {pat}: {nxts} -> R: {nxts.get('R',0)/tot*100:.1f}%, B: {nxts.get('B',0)/tot*100:.1f}%")

# Order 3 Transitions:
o3_counts = {}
for _, outs in sessions:
    nz = [o for o in outs if o != "ZERO"]
    for i in range(3, len(nz)):
        pat = f"{nz[i-3][0]}{nz[i-2][0]}{nz[i-1][0]}"
        nxt = nz[i][0]
        o3_counts.setdefault(pat, {})[nxt] = o3_counts.setdefault(pat, {}).get(nxt, 0) + 1

print("\nOrder 3 Transitions (Top patterns):")
for pat, nxts in sorted(o3_counts.items()):
    tot = sum(nxts.values())
    if tot >= 50:
        print(f"  Pattern {pat} (n={tot:3d}): R: {nxts.get('R',0)/tot*100:.1f}%, B: {nxts.get('B',0)/tot*100:.1f}%")
