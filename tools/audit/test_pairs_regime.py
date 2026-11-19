"""
Empirical test of the Pairs Regime Detector across all 49 sessions.
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()

# Let's test:
# At each non-zero spin t:
# Maintain list of recent completed streak lengths
# Calculate pair_ratio_recent (over last 8 completed streaks)
# Test:
# 1. When pair_ratio_recent >= 0.35 and s == 1: what is P(Cont -> 2)?
# 2. When pair_ratio_recent >= 0.35 and s == 2: what is P(Break -> opp)?
# 3. When pair_ratio_recent < 0.20 (low pairs, e.g. pure zebra or deep trends): what is P(Cont vs Break)?

res_s1_high_pair = {'cont': 0, 'break': 0}
res_s1_low_pair = {'cont': 0, 'break': 0}

res_s2_high_pair = {'cont': 0, 'break': 0}
res_s2_low_pair = {'cont': 0, 'break': 0}

for s_idx, sess in enumerate(sessions):
    outs = sess['outcomes']
    nz = [x for x in outs if x != 'ZERO']
    if len(nz) < 15: continue
    
    # We walk spin by spin
    completed_streaks = [] # list of lengths
    hist_nz = [nz[0]]
    
    for i in range(1, len(nz)):
        actual = nz[i]
        cur_col = hist_nz[-1]
        
        # Current active streak length
        s = 1
        for k in range(len(hist_nz) - 2, -1, -1):
            if hist_nz[k] == cur_col: s += 1
            else: break
            
        # Recent pairs ratio over last 6-8 completed streaks
        recent_st = completed_streaks[-8:] if len(completed_streaks) >= 4 else completed_streaks
        pairs_in_recent = sum(1 for sl in recent_st if sl == 2)
        pair_ratio = (pairs_in_recent / len(recent_st)) if recent_st else 0.25
        
        did_cont = (actual == cur_col)
        
        if s == 1:
            if pair_ratio >= 0.35:
                if did_cont: res_s1_high_pair['cont'] += 1
                else: res_s1_high_pair['break'] += 1
            elif pair_ratio <= 0.20:
                if did_cont: res_s1_low_pair['cont'] += 1
                else: res_s1_low_pair['break'] += 1
        elif s == 2:
            if pair_ratio >= 0.35:
                if did_cont: res_s2_high_pair['cont'] += 1
                else: res_s2_high_pair['break'] += 1
            elif pair_ratio <= 0.20:
                if did_cont: res_s2_low_pair['cont'] += 1
                else: res_s2_low_pair['break'] += 1
                
        # If this spin breaks the streak, record the completed streak
        if actual != cur_col:
            completed_streaks.append(s)
            
        hist_nz.append(actual)

print("="*75)
print(" PAIRS REGIME EMPIRICAL TRANSITION TEST (N = 49 SESSIONS)")
print("="*75)
t1_h = res_s1_high_pair['cont'] + res_s1_high_pair['break']
t1_l = res_s1_low_pair['cont'] + res_s1_low_pair['break']
p1_h = res_s1_high_pair['cont'] / t1_h * 100 if t1_h else 0
p1_l = res_s1_low_pair['cont'] / t1_l * 100 if t1_l else 0

print(f"When Current Streak s = 1 (Single):")
print(f"  When Recent Pairs Ratio >= 35% (Elevated Pairs, N={t1_h}):")
print(f"    P(Cont -> forms PAIR) = {p1_h:.2f}%, P(Break -> Alt) = {100-p1_h:.2f}%")
print(f"  When Recent Pairs Ratio <= 20% (Low Pairs, N={t1_l}):")
print(f"    P(Cont -> forms PAIR) = {p1_l:.2f}%, P(Break -> Alt) = {100-p1_l:.2f}%")

t2_h = res_s2_high_pair['cont'] + res_s2_high_pair['break']
t2_l = res_s2_low_pair['cont'] + res_s2_low_pair['break']
p2_h_brk = res_s2_high_pair['break'] / t2_h * 100 if t2_h else 0
p2_l_brk = res_s2_low_pair['break'] / t2_l * 100 if t2_l else 0

print(f"\nWhen Current Streak s = 2 (Pair):")
print(f"  When Recent Pairs Ratio >= 35% (Elevated Pairs, N={t2_h}):")
print(f"    P(BREAK PAIR -> switch) = {p2_h_brk:.2f}%, P(Cont to 3) = {100-p2_h_brk:.2f}%")
print(f"  When Recent Pairs Ratio <= 20% (Low Pairs, N={t2_l}):")
print(f"    P(BREAK PAIR -> switch) = {p2_l_brk:.2f}%, P(Cont to 3) = {100-p2_l_brk:.2f}%")
