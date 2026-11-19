"""
Research & Validation of Core Mathematical Hypotheses for v16.1 APEX-Neural.
Tests:
1. Average Streak Length dynamics (RED vs BLACK rolling averages)
2. Previous opposite streak memory (pair-to-pair resonance: 2-2-2 patterns)
3. Direct Win Rate on Streak=1 and Streak=2 under different predictors
4. Feature ablation & replacement of noisy high-lags with Streak-Mood metrics
"""
import glob, json, math, os, sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions for analysis.")

# --- 1. Empirical Analysis of Streak=1 and Streak=2 transitions ---
# Let's inspect all streak=1 and streak=2 transitions across all 49 sessions
# and correlate with avg_streak of that color, alternation rate, and prev_streak_len

streak_events = [] # list of dicts

for s_idx, sess in enumerate(sessions):
    outs = sess['outcomes']
    nz = [x for x in outs if x != 'ZERO']
    if len(nz) < 10: continue
    
    # Track streaks and their lengths
    st_history = [] # list of (color, length)
    cur_c = nz[0]
    cur_len = 1
    for i in range(1, len(nz)):
        if nz[i] == cur_c:
            cur_len += 1
        else:
            st_history.append((cur_c, cur_len))
            cur_c = nz[i]
            cur_len = 1
    st_history.append((cur_c, cur_len))
    
    # Now walk spin by spin
    hist_nz = []
    for i in range(len(nz) - 1):
        hist_nz.append(nz[i])
        actual_next = nz[i+1]
        
        cur_col = hist_nz[-1]
        s = 1
        for k in range(len(hist_nz) - 2, -1, -1):
            if hist_nz[k] == cur_col: s += 1
            else: break
            
        # Find previous completed streak
        prev_st_col = None
        prev_st_len = None
        idx_prev = len(hist_nz) - 1 - s
        if idx_prev >= 0:
            prev_st_col = hist_nz[idx_prev]
            prev_st_len = 1
            for k in range(idx_prev - 1, -1, -1):
                if hist_nz[k] == prev_st_col: prev_st_len += 1
                else: break
                
        # Calculate rolling average streak length for RED and BLACK over last 24 spins
        w24 = hist_nz[-24:]
        st_r, st_b = [], []
        if w24:
            tc = w24[0]; tl = 1
            for j in range(1, len(w24)):
                if w24[j] == tc: tl += 1
                else:
                    if tc == 'RED': st_r.append(tl)
                    else: st_b.append(tl)
                    tc = w24[j]; tl = 1
            if tc == 'RED': st_r.append(tl)
            else: st_b.append(tl)
            
        avg_r = sum(st_r) / len(st_r) if st_r else 1.5
        avg_b = sum(st_b) / len(st_b) if st_b else 1.5
        avg_cur = avg_r if cur_col == 'RED' else avg_b
        avg_opp = avg_b if cur_col == 'RED' else avg_r
        
        # Alternation in last 8 non-zero
        w8 = hist_nz[-8:]
        trans = sum(1 for j in range(1, len(w8)) if w8[j] != w8[j-1])
        alt8 = trans / max(1, len(w8) - 1)
        
        streak_events.append({
            'sess': s_idx,
            'color': cur_col,
            'streak': s,
            'prev_st_len': prev_st_len,
            'avg_cur': avg_cur,
            'avg_opp': avg_opp,
            'avg_diff': avg_cur - avg_opp,
            'alt8': alt8,
            'actual_next': actual_next,
            'did_cont': (actual_next == cur_col)
        })

print(f"Total evaluated streak transitions: {len(streak_events)}")

# 1. When Streak == 1: When does it continue (pair) vs break (alternation)?
s1 = [e for e in streak_events if e['streak'] == 1]
print(f"\n--- Streak == 1 Analysis (N = {len(s1)}) ---")
print(f"Base P(Cont/Pair) = {sum(1 for e in s1 if e['did_cont'])/len(s1)*100:.2f}% | P(Break/Alt) = {sum(1 for e in s1 if not e['did_cont'])/len(s1)*100:.2f}%")

# Conditioned on Previous Streak Length:
# If prev_st_len == 2 (did the previous color just form a pair? Does server do 2-2 pairs?)
p2 = [e for e in s1 if e['prev_st_len'] == 2]
p1 = [e for e in s1 if e['prev_st_len'] == 1]
p3 = [e for e in s1 if e['prev_st_len'] is not None and e['prev_st_len'] >= 3]

print("\nConditioned on Previous Color's Streak Length:")
if p2:
    p2_c = sum(1 for e in p2 if e['did_cont']) / len(p2) * 100
    print(f"  When Prev Color was a PAIR (len=2, N={len(p2)}): P(Current forms PAIR) = {p2_c:.2f}%, P(Break) = {100-p2_c:.2f}%")
if p1:
    p1_c = sum(1 for e in p1 if e['did_cont']) / len(p1) * 100
    print(f"  When Prev Color was a SINGLE (len=1, N={len(p1)}): P(Current forms PAIR) = {p1_c:.2f}%, P(Break) = {100-p1_c:.2f}%")
if p3:
    p3_c = sum(1 for e in p3 if e['did_cont']) / len(p3) * 100
    print(f"  When Prev Color was DEEP (len>=3, N={len(p3)}): P(Current forms PAIR) = {p3_c:.2f}%, P(Break) = {100-p3_c:.2f}%")

# Conditioned on Rolling Avg Streak of Current Color:
s1_high_avg = [e for e in s1 if e['avg_cur'] >= 1.8]
s1_low_avg = [e for e in s1 if e['avg_cur'] < 1.4]
if s1_high_avg:
    c = sum(1 for e in s1_high_avg if e['did_cont']) / len(s1_high_avg) * 100
    print(f"\nConditioned on Rolling Avg Streak of Current Color:")
    print(f"  When AvgStreak >= 1.8 (N={len(s1_high_avg)}): P(Cont/Pair) = {c:.2f}%, P(Break) = {100-c:.2f}%")
if s1_low_avg:
    c = sum(1 for e in s1_low_avg if e['did_cont']) / len(s1_low_avg) * 100
    print(f"  When AvgStreak < 1.4 (N={len(s1_low_avg)}): P(Cont/Pair) = {c:.2f}%, P(Break) = {100-c:.2f}%")

# 2. When Streak == 2: When does it continue (triple) vs break (pair break)?
s2 = [e for e in streak_events if e['streak'] == 2]
print(f"\n--- Streak == 2 Analysis (N = {len(s2)}) ---")
print(f"Base P(Cont to 3) = {sum(1 for e in s2 if e['did_cont'])/len(s2)*100:.2f}% | P(Break pair) = {sum(1 for e in s2 if not e['did_cont'])/len(s2)*100:.2f}%")

# Conditioned on Previous Streak Length:
s2_p2 = [e for e in s2 if e['prev_st_len'] == 2]
s2_p1 = [e for e in s2 if e['prev_st_len'] == 1]
s2_p3 = [e for e in s2 if e['prev_st_len'] is not None and e['prev_st_len'] >= 3]

print("\nConditioned on Previous Color's Streak Length:")
if s2_p2:
    c = sum(1 for e in s2_p2 if e['did_cont']) / len(s2_p2) * 100
    print(f"  When Prev Color was a PAIR (2-2 pattern? N={len(s2_p2)}): P(Cont to 3) = {c:.2f}%, P(BREAK PAIR) = {100-c:.2f}%")
if s2_p1:
    c = sum(1 for e in s2_p1 if e['did_cont']) / len(s2_p1) * 100
    print(f"  When Prev Color was a SINGLE (1-2 pattern, N={len(s2_p1)}): P(Cont to 3) = {c:.2f}%, P(Break) = {100-c:.2f}%")
if s2_p3:
    c = sum(1 for e in s2_p3 if e['did_cont']) / len(s2_p3) * 100
    print(f"  When Prev Color was DEEP (N={len(s2_p3)}): P(Cont to 3) = {c:.2f}%, P(Break) = {100-c:.2f}%")

# Conditioned on Rolling Avg Streak of Current Color:
s2_high_avg = [e for e in s2 if e['avg_cur'] >= 2.2]
s2_low_avg = [e for e in s2 if e['avg_cur'] < 1.7]
if s2_high_avg:
    c = sum(1 for e in s2_high_avg if e['did_cont']) / len(s2_high_avg) * 100
    print(f"\nConditioned on Rolling Avg Streak of Current Color:")
    print(f"  When AvgStreak >= 2.2 (N={len(s2_high_avg)}): P(Cont to 3) = {c:.2f}%, P(Break) = {100-c:.2f}%")
if s2_low_avg:
    c = sum(1 for e in s2_low_avg if e['did_cont']) / len(s2_low_avg) * 100
    print(f"  When AvgStreak < 1.7 (N={len(s2_low_avg)}): P(Cont to 3) = {c:.2f}%, P(BREAK PAIR) = {100-c:.2f}%")

# Conditioned on Local Alternation Rate when Streak == 2:
s2_hi_alt = [e for e in s2 if e['alt8'] >= 0.70]
s2_lo_alt = [e for e in s2 if e['alt8'] <= 0.40]
if s2_hi_alt:
    c = sum(1 for e in s2_hi_alt if e['did_cont']) / len(s2_hi_alt) * 100
    print(f"\nConditioned on Local Alternation (w=8):")
    print(f"  When AltRate >= 0.70 (N={len(s2_hi_alt)}): P(Cont to 3) = {c:.2f}%, P(BREAK PAIR) = {100-c:.2f}%")
if s2_lo_alt:
    c = sum(1 for e in s2_lo_alt if e['did_cont']) / len(s2_lo_alt) * 100
    print(f"  When AltRate <= 0.40 (N={len(s2_lo_alt)}): P(Cont to 3) = {c:.2f}%, P(Break) = {100-c:.2f}%")
