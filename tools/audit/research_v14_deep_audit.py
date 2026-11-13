import glob
import hashlib
import json
import math
import os
import random
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round
from parity_ts_vs_python import predict_v13

# Load all 29 clean sessions
def load_all_29():
    paths = sorted(
        glob.glob(r"D:\Vibe\matreshka-quantum\log storage\*.json")
        + [r"D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json"]
        + glob.glob(r"D:\Downloads\matreshka*.json")
        + glob.glob(r"D:\Downloads\quantum*.json")
    )
    skip = {
        "matreshka_session_2026-03-31.json",
        "matreshka_session_2026-04-01 (3).json",
        "matreshka_session_2026-03-31 (1).json",
        "matreshka_session_2026-03-31 (2).json",
        "matreshka_session_2026-03-31 (3).json",
    }
    res, seen = [], set()
    for p in paths:
        if not os.path.exists(p):
            continue
        fn = os.path.basename(p)
        if fn in skip:
            continue
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        logs = d.get("logs", []) if isinstance(d, dict) else d
        if fn == "matreshka_quantum_v11_2026-11-08.json":
            logs = logs[:22]
        outs = [e.get("input_result") or e.get("actual_outcome") or e.get("outcome") for e in logs]
        outs = [x for x in outs if x in ("RED", "BLACK", "ZERO")]
        h = hashlib.md5(",".join(outs).encode()).hexdigest()
        if outs and h not in seen:
            seen.add(h)
            res.append((fn, outs))
    return res

sessions = load_all_29()
print(f"Total clean sessions loaded: {len(sessions)}")

# 1. Overall stats across all 29 sessions
tot_spins = sum(len(o) for _, o in sessions)
tot_zeros = sum(o.count("ZERO") for _, o in sessions)
tot_reds = sum(o.count("RED") for _, o in sessions)
tot_blacks = sum(o.count("BLACK") for _, o in sessions)
print(f"Total spins: {tot_spins:,}")
print(f"Reds: {tot_reds:,} ({tot_reds/tot_spins*100:.2f}%)")
print(f"Blacks: {tot_blacks:,} ({tot_blacks/tot_spins*100:.2f}%)")
print(f"Zeros: {tot_zeros:,} ({tot_zeros/tot_spins*100:.2f}%)")

# 2. Test v13 predictor on all 29 sessions
wins_all = 0
wins_nz = 0
nz_spins = tot_spins - tot_zeros
per_sess_rates = []

for fn, outs in sessions:
    hist = []
    w = 0
    nz = 0
    for o in outs:
        pred = predict_v13(hist, window=15, min_cmax=3)
        if o == pred:
            w += 1
            wins_all += 1
        if o != "ZERO":
            nz += 1
            if o == pred:
                wins_nz += 1
        hist.append(o)
    rate = w / len(outs) * 100
    rate_nz = w / nz * 100 if nz > 0 else 0
    per_sess_rates.append((fn, len(outs), rate, rate_nz))

print(f"\nv13 Predictor Overall Winrate (all 29 sessions): {wins_all/tot_spins*100:.2f}% ({wins_all:,}/{tot_spins:,})")
print(f"v13 Predictor Non-Zero Winrate: {wins_nz/nz_spins*100:.2f}% ({wins_nz:,}/{nz_spins:,})")

# Specifically check nov12 session
nov12_entry = [x for x in per_sess_rates if "2026-11-12" in x[0]][0]
print(f"\nSession Nov 12 stats: Spins={nov12_entry[1]}, WinRate={nov12_entry[2]:.2f}%, Non-Zero={nov12_entry[3]:.2f}%")

# Let's inspect win rate by step in real play
# Using TURBO_HARVEST engine trace on Nov 12
nov12_outs = [o for fn, o in sessions if "2026-11-12" in fn][0]
with open(r"d:\Downloads\matreshka_session_2026-11-12.json", "r", encoding="utf-8") as f:
    nov12_json = json.load(f)["logs"]

step_wins = {}
step_totals = {}
for e in nov12_json:
    st = e["current_step"]
    step_totals[st] = step_totals.get(st, 0) + 1
    if e["is_win"]:
        step_wins[st] = step_wins.get(st, 0) + 1

print("\nNov 12 Win Rate By Step:")
for st in sorted(step_totals):
    w = step_wins.get(st, 0)
    t = step_totals[st]
    print(f"  Step {st:2d}: {w:2d}/{t:2d} wins ({w/t*100:5.1f}%)")
