import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_v14_deep_audit import load_all_29

sessions = load_all_29()

rule_stats = {}

for fn, outs in sessions:
    hist = []
    for o in outs:
        if not hist:
            hist.append(o)
            continue
        pred_res = PrngDetectorMirror.get_recommendation_and_confidence(hist)
        rule_name = pred_res[2]  # state / reason
        pred_col = pred_res[0]
        is_nz = o != "ZERO"
        is_win = o == pred_col and is_nz

        st = rule_stats.setdefault(
            rule_name,
            {"total": 0, "nz": 0, "wins": 0, "zeros": 0, "losses": 0},
        )
        st["total"] += 1
        if is_nz:
            st["nz"] += 1
            if is_win:
                st["wins"] += 1
            else:
                st["losses"] += 1
        else:
            st["zeros"] += 1

        hist.append(o)

print("=== RULE-BY-RULE AUDIT ACROSS ALL 29 CLEAN SESSIONS (2,711 SPINS) ===")
print(
    f"{'Rule / State Name':30s} | {'Total':5s} | {'NZ':5s} | {'Wins':5s} | "
    f"{'Overall W%':10s} | {'Non-Zero W%':11s} | {'Zeros':5s}"
)
print("-" * 88)
total_sp = 0
total_wins = 0
total_nz = 0
for r_name, s in sorted(rule_stats.items(), key=lambda x: -x[1]["total"]):
    tot = s["total"]
    nz = s["nz"]
    w = s["wins"]
    z = s["zeros"]
    ow = w / tot * 100 if tot > 0 else 0
    nzw = w / nz * 100 if nz > 0 else 0
    total_sp += tot
    total_wins += w
    total_nz += nz
    print(
        f"{r_name:30s} | {tot:5d} | {nz:5d} | {w:5d} | "
        f"{ow:9.2f}% | {nzw:10.2f}% | {z:5d}"
    )

print("-" * 88)
print(
    f"{'TOTAL / AVERAGE':30s} | {total_sp:5d} | {total_nz:5d} | {total_wins:5d} | "
    f"{total_wins/total_sp*100:9.2f}% | {total_wins/total_nz*100:10.2f}%"
)
