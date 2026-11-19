"""
Comprehensive Empirical Research on Streak Mechanics & Server Regimes across ALL Sessions.
"""
import glob, json, math, os, sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

# Collect all non-zero streak events across all sessions
# For every streak of length s, does it continue to s+1 or break?
# Conditioned on:
# - Streak length s (1, 2, 3, 4, 5, 6+)
# - Color (RED vs BLACK)
# - Rolling average streak length (short < 1.6, medium 1.6-2.0, long > 2.0)
# - Rolling alternation rate (low < 0.45, normal 0.45-0.55, high > 0.55)

stats_by_length = defaultdict(lambda: {'cont': 0, 'break': 0})
stats_by_length_and_color = defaultdict(lambda: {'cont': 0, 'break': 0})
stats_conditioned_avg_streak = defaultdict(lambda: {'cont': 0, 'break': 0})
stats_conditioned_alt_rate = defaultdict(lambda: {'cont': 0, 'break': 0})

all_streaks_red = []
all_streaks_black = []

for s_idx, sess in enumerate(sessions):
    outs = sess['outcomes']
    nz = [x for x in outs if x != 'ZERO']
    
    # Track streaks in nz
    if not nz: continue
    
    # First extract full streak sequence
    streaks = [] # list of (color, length)
    cur_c = nz[0]
    cur_len = 1
    for i in range(1, len(nz)):
        if nz[i] == cur_c:
            cur_len += 1
        else:
            streaks.append((cur_c, cur_len))
            if cur_c == 'RED': all_streaks_red.append(cur_len)
            else: all_streaks_black.append(cur_len)
            cur_c = nz[i]
            cur_len = 1
    streaks.append((cur_c, cur_len))
    if cur_c == 'RED': all_streaks_red.append(cur_len)
    else: all_streaks_black.append(cur_len)

    # Now step through spin-by-spin to calculate rolling context
    hist_nz = []
    for i in range(len(nz) - 1):
        hist_nz.append(nz[i])
        actual_next = nz[i+1]
        
        # Current active streak up to i
        cur_color = hist_nz[-1]
        s = 1
        for k in range(len(hist_nz) - 2, -1, -1):
            if hist_nz[k] == cur_color: s += 1
            else: break
            
        did_cont = (actual_next == cur_color)
        
        # Rolling average streak length over last 20 non-zero spins
        w20 = hist_nz[-20:]
        st_lens_r = []
        st_lens_b = []
        c_tmp = w20[0]
        l_tmp = 1
        for j in range(1, len(w20)):
            if w20[j] == c_tmp: l_tmp += 1
            else:
                if c_tmp == 'RED': st_lens_r.append(l_tmp)
                else: st_lens_b.append(l_tmp)
                c_tmp = w20[j]
                l_tmp = 1
        if c_tmp == 'RED': st_lens_r.append(l_tmp)
        else: st_lens_b.append(l_tmp)
        
        avg_s = (sum(st_lens_r) + sum(st_lens_b)) / max(1, len(st_lens_r) + len(st_lens_b))
        avg_s_cur = (sum(st_lens_r) / len(st_lens_r)) if cur_color == 'RED' and st_lens_r else ((sum(st_lens_b) / len(st_lens_b)) if cur_color == 'BLACK' and st_lens_b else avg_s)
        
        # Alternation in last 10 spins
        w10 = hist_nz[-10:]
        trans = sum(1 for j in range(1, len(w10)) if w10[j] != w10[j-1])
        alt_rate = trans / max(1, len(w10) - 1)
        
        # Binning
        s_key = min(s, 6)
        if did_cont:
            stats_by_length[s_key]['cont'] += 1
            stats_by_length_and_color[(s_key, cur_color)]['cont'] += 1
        else:
            stats_by_length[s_key]['break'] += 1
            stats_by_length_and_color[(s_key, cur_color)]['break'] += 1
            
        avg_bin = 'SHORT (<1.7)' if avg_s_cur < 1.7 else ('MED (1.7-2.2)' if avg_s_cur <= 2.2 else 'LONG (>2.2)')
        alt_bin = 'LOW_ALT (<0.45)' if alt_rate < 0.45 else ('NORM_ALT (0.45-0.65)' if alt_rate <= 0.65 else 'HIGH_ALT (>0.65)')
        
        if did_cont:
            stats_conditioned_avg_streak[(s_key, avg_bin)]['cont'] += 1
            stats_conditioned_alt_rate[(s_key, alt_bin)]['cont'] += 1
        else:
            stats_conditioned_avg_streak[(s_key, avg_bin)]['break'] += 1
            stats_conditioned_alt_rate[(s_key, alt_bin)]['break'] += 1

print("\n" + "="*80)
print(" 1. GLOBAL STREAK CONTINUATION PROBABILITIES (P(Streak >= s+1 | Streak >= s))")
print("="*80)
print(f"{'Streak s':<10} {'Cont':>8} {'Break':>8} {'Total':>8} {'P(Cont) %':>12} {'P(Break) %':>12}")
print("-" * 60)
for s in range(1, 7):
    d = stats_by_length[s]
    tot = d['cont'] + d['break']
    p_c = d['cont'] / tot * 100 if tot else 0
    p_b = d['break'] / tot * 100 if tot else 0
    s_label = f"s = {s}" if s < 6 else "s >= 6"
    print(f"{s_label:<10} {d['cont']:>8} {d['break']:>8} {tot:>8} {p_c:>11.2f}% {p_b:>11.2f}%")

print("\n" + "="*80)
print(" 2. STREAK CONTINUATION BY COLOR (RED vs BLACK)")
print("="*80)
for c in ['RED', 'BLACK']:
    print(f"--- Color: {c} ---")
    for s in range(1, 5):
        d = stats_by_length_and_color[(s, c)]
        tot = d['cont'] + d['break']
        p_c = d['cont'] / tot * 100 if tot else 0
        s_label = f"s = {s}"
        print(f"  {s_label:<8}: Cont = {d['cont']:>5}, Break = {d['break']:>5}, P(Cont) = {p_c:.2f}%")

print("\n" + "="*80)
print(" 3. CONDITIONED ON ROLLING AVG STREAK LENGTH OF COLOR")
print("="*80)
for s in [1, 2, 3]:
    print(f"--- When Current Streak s = {s} ---")
    for avg_bin in ['SHORT (<1.7)', 'MED (1.7-2.2)', 'LONG (>2.2)']:
        d = stats_conditioned_avg_streak[(s, avg_bin)]
        tot = d['cont'] + d['break']
        p_c = d['cont'] / tot * 100 if tot else 0
        p_b = d['break'] / tot * 100 if tot else 0
        print(f"  AvgStreak {avg_bin:<16}: Cont={d['cont']:>5}, Break={d['break']:>5}, P(Cont)={p_c:>6.2f}%, P(Break)={p_b:>6.2f}%")

print("\n" + "="*80)
print(" 4. CONDITIONED ON ROLLING ALTERNATION RATE")
print("="*80)
for s in [1, 2, 3]:
    print(f"--- When Current Streak s = {s} ---")
    for alt_bin in ['LOW_ALT (<0.45)', 'NORM_ALT (0.45-0.65)', 'HIGH_ALT (>0.65)']:
        d = stats_conditioned_alt_rate[(s, alt_bin)]
        tot = d['cont'] + d['break']
        p_c = d['cont'] / tot * 100 if tot else 0
        p_b = d['break'] / tot * 100 if tot else 0
        print(f"  AltRate {alt_bin:<20}: Cont={d['cont']:>5}, Break={d['break']:>5}, P(Cont)={p_c:>6.2f}%, P(Break)={p_b:>6.2f}%")
