"""
Test streak transition win rates conditioned on (streak >= avg_streak_color)
across all 49 sessions (6,433 spins).
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()

# At each spin where streak == 2:
# Calculate rolling average streak length of current color in last 24 non-zero spins
# Compare:
# Case 1: avg_streak_cur < 2.0 (server in short-series mood)
# Case 2: avg_streak_cur >= 2.0 (server in long-series mood)

s2_short_cont = 0
s2_short_break = 0
s2_long_cont = 0
s2_long_break = 0

s1_short_cont = 0
s1_short_break = 0
s1_long_cont = 0
s1_long_break = 0

for sess in sessions:
    nz = [x for x in sess['outcomes'] if x != 'ZERO']
    if len(nz) < 15: continue
    
    for i in range(10, len(nz) - 1):
        hist_nz = nz[:i+1]
        actual = nz[i+1]
        cur_col = hist_nz[-1]
        
        # Current streak
        s = 1
        for k in range(len(hist_nz) - 2, -1, -1):
            if hist_nz[k] == cur_col: s += 1
            else: break
            
        # Rolling average streak of cur_col in last 24 spins
        w24 = hist_nz[-24:]
        st_cur = []
        tc = w24[0]; tl = 1
        for j in range(1, len(w24)):
            if w24[j] == tc: tl += 1
            else:
                if tc == cur_col: st_cur.append(tl)
                tc = w24[j]; tl = 1
        if tc == cur_col: st_cur.append(tl)
        
        avg_cur = sum(st_cur) / len(st_cur) if st_cur else 2.0
        did_cont = (actual == cur_col)
        
        if s == 2:
            if avg_cur < 1.95:
                if did_cont: s2_short_cont += 1
                else: s2_short_break += 1
            else:
                if did_cont: s2_long_cont += 1
                else: s2_long_break += 1
        elif s == 1:
            if avg_cur < 1.70:
                if did_cont: s1_short_cont += 1
                else: s1_short_break += 1
            else:
                if did_cont: s1_long_cont += 1
                else: s1_long_break += 1

print("="*75)
print(" STREAK DECISION CALIBRATION BY ROLLING AVG STREAK OF COLOR")
print("="*75)
tot_s2_short = s2_short_cont + s2_short_break
tot_s2_long = s2_long_cont + s2_long_break
p_s2_s_brk = s2_short_break / tot_s2_short * 100 if tot_s2_short else 0
p_s2_l_cont = s2_long_cont / tot_s2_long * 100 if tot_s2_long else 0

print(f"When Streak == 2 (A Pair has formed):")
print(f"  When AvgStreak < 1.95 (Short Mood, N={tot_s2_short}):")
print(f"    P(BREAK PAIR) = {p_s2_s_brk:.2f}% | P(Cont to 3) = {100-p_s2_s_brk:.2f}%")
print(f"  When AvgStreak >= 1.95 (Normal/Long Mood, N={tot_s2_long}):")
print(f"    P(Cont to 3)  = {p_s2_l_cont:.2f}% | P(Break pair) = {100-p_s2_l_cont:.2f}%")

tot_s1_short = s1_short_cont + s1_short_break
tot_s1_long = s1_long_cont + s1_long_break
p_s1_s_brk = s1_short_break / tot_s1_short * 100 if tot_s1_short else 0

print(f"\nWhen Streak == 1 (Single):")
print(f"  When AvgStreak < 1.70 (Very Short/Zebra Mood, N={tot_s1_short}):")
print(f"    P(BREAK/ALTERNATE) = {p_s1_s_brk:.2f}% | P(Cont to 2) = {100-p_s1_s_brk:.2f}%")
print(f"  When AvgStreak >= 1.70 (Normal/Long Mood, N={tot_s1_long}):")
print(f"    P(Cont to 2) = {s1_long_cont/tot_s1_long*100:.2f}% | P(Break) = {s1_long_break/tot_s1_long*100:.2f}%")
