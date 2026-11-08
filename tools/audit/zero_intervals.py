import json
import math
import sys
import numpy as np

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Projects\MTCasinoScript\tools\audit\normalized_spins.json", "r", encoding="utf-8") as f:
    spins = json.load(f)

# Group by session
sessions = {}
for s in spins:
    sid = s["session_id"]
    if sid not in sessions:
        sessions[sid] = []
    sessions[sid].append(s)

zero_intervals = []
for sid, s_list in sessions.items():
    last_z = None
    for idx, s in enumerate(s_list):
        if s["outcome"] == "ZERO":
            if last_z is not None:
                zero_intervals.append(idx - last_z)
            last_z = idx

print(f"Total zero intervals within sessions: {len(zero_intervals)}")
print(f"Mean interval between zeroes: {np.mean(zero_intervals):.2f} spins (Theoretical 1/p = {1/0.0528:.2f})")
print(f"Median interval: {np.median(zero_intervals):.1f}")
print(f"Min interval: {np.min(zero_intervals)}")
print(f"Max interval: {np.max(zero_intervals)}")
print(f"StdDev: {np.std(zero_intervals):.2f}")

# Distribution of intervals
print("\nIntervals breakdown:")
for b_low, b_high in [(1, 3), (4, 10), (11, 20), (21, 40), (41, 100)]:
    cnt = sum(1 for iv in zero_intervals if b_low <= iv <= b_high)
    print(f"  [{b_low:2d} - {b_high:3d} spins]: {cnt:2d} ({cnt/len(zero_intervals)*100:5.1f}%)")
