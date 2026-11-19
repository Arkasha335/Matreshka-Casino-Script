"""
Test the Dynamic Streak Saturation Law on session_20261117_165453.jsonl
and across all 49 sessions.
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()
fresh_sess = [s for s in sessions if '20261117' in s['file']][0]
print(f"Loaded fresh session: {fresh_sess['file']} with {len(fresh_sess['outcomes'])} spins.")

# Let's simulate spins 320 to 335 with the Streak Saturation Law
lines = [json.loads(l) for l in open('bot/logs/session_20261117_165453.jsonl', encoding='utf-8') if l.strip()]

def get_rolling_avg_streak(hist, color, window=24):
    nz = [x for x in hist if x != 'ZERO']
    w = nz[-window:]
    if not w: return 1.8
    st = []
    tc = w[0]; tl = 1
    for j in range(1, len(w)):
        if w[j] == tc: tl += 1
        else:
            if tc == color: st.append(tl)
            tc = w[j]; tl = 1
    if tc == color: st.append(tl)
    return sum(st)/len(st) if st else 1.8

hist = [l['outcome'] for l in lines]

print("\n--- Testing Streak Saturation on Spins 326 to 333 of Fresh Session ---")
for sp in range(326, 334):
    sub = hist[:sp-1]
    nz = [x for x in sub if x != 'ZERO']
    actual = hist[sp-1]
    cur_c = nz[-1]
    opp_c = 'BLACK' if cur_c == 'RED' else 'RED'
    
    # Calculate streak
    s = 1
    for k in range(len(nz)-2, -1, -1):
        if nz[k] == cur_c: s += 1
        else: break
        
    avg_cur = get_rolling_avg_streak(sub, cur_c, window=24)
    sat_ratio = s / avg_cur
    
    # Under Saturation Law:
    # If sat_ratio >= 1.0 -> Expect Break (opp_c)
    # If sat_ratio < 0.85 -> Expect Cont (cur_c)
    # Else neutral
    if sat_ratio >= 1.0:
        sat_rec = opp_c
        sat_reason = f"SATURATED (s={s} >= avg={avg_cur:.2f}, ratio={sat_ratio:.2f}) -> FADE"
    else:
        sat_rec = cur_c
        sat_reason = f"UNSATURATED (s={s} < avg={avg_cur:.2f}, ratio={sat_ratio:.2f}) -> CONT"
        
    print(f"Spin #{sp} | Streak: {s} {cur_c:<5} | Avg_{cur_c}: {avg_cur:.2f} | Sat: {sat_ratio:.2f} | Rec: {sat_rec:<5} | Out: {actual:<5} | {'WIN!' if actual == sat_rec else 'LOSS'}")
