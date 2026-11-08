import json
import math
import sys
import numpy as np

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Projects\MTCasinoScript\tools\audit\normalized_spins.json", "r", encoding="utf-8") as f:
    spins = json.load(f)

sessions = {}
for s in spins:
    sid = s["session_id"]
    if sid not in sessions:
        sessions[sid] = []
    sessions[sid].append(s)

print("--- Testing Homogeneity Across Sessions ---")
print(f"{'Session ID':<30} | {'Spins':<6} | {'Red %':<8} | {'Black %':<8} | {'Zero %':<8} | {'P-val Zero':<10}")
print("-" * 80)

# Global Zero rate
global_zeros = sum(1 for s in spins if s["outcome"] == "ZERO")
p_zero_global = global_zeros / len(spins)

for sid, s_list in sessions.items():
    n = len(s_list)
    reds = sum(1 for s in s_list if s["outcome"] == "RED")
    blacks = sum(1 for s in s_list if s["outcome"] == "BLACK")
    zeros = sum(1 for s in s_list if s["outcome"] == "ZERO")
    
    # Binomial test for zero rate vs global
    # Normal approx
    se = math.sqrt(p_zero_global * (1 - p_zero_global) / n)
    z = (zeros / n - p_zero_global) / se if se > 0 else 0
    p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    
    print(f"{sid:<30} | {n:<6} | {reds/n*100:>7.1f}% | {blacks/n*100:>7.1f}% | {zeros/n*100:>7.1f}% | {p_val:>9.4f}")
