import glob, json, os, sys
from collections import defaultdict, Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

# Collect all non-zero runs
streak_counts = defaultdict(lambda: {'cont': 0, 'break': 0, 'zero': 0})

for s in sessions:
    outs = s['outcomes']
    for i in range(1, len(outs)):
        # What was the current streak up to i-1?
        if outs[i-1] in ('RED', 'BLACK'):
            c = outs[i-1]
            s_len = 1
            for k in range(i-2, -1, -1):
                if outs[k] == c: s_len += 1
                else: break
                
            nxt = outs[i]
            if nxt == c:
                streak_counts[s_len]['cont'] += 1
            elif nxt == 'ZERO':
                streak_counts[s_len]['zero'] += 1
            else:
                streak_counts[s_len]['break'] += 1

print("\n--- Empirical Streak Continuation vs Break Rates across All 6,773 Spins ---")
print(f"{'Streak Len':10s} | {'Total':6s} | {'Continue':8s} | {'Break':8s} | {'Zero':6s} | {'Cont Rate (excl Zero)':22s} | {'Break Rate (excl Zero)':22s}")
print("-" * 95)
for s_len in range(1, 11):
    d = streak_counts[s_len]
    tot = d['cont'] + d['break'] + d['zero']
    if tot == 0: continue
    nz_tot = d['cont'] + d['break']
    cont_rate = d['cont'] / nz_tot * 100 if nz_tot else 0
    break_rate = d['break'] / nz_tot * 100 if nz_tot else 0
    print(f"{s_len:10d} | {tot:6d} | {d['cont']:8d} | {d['break']:8d} | {d['zero']:6d} | {cont_rate:5.2f}%                 | {break_rate:5.2f}%")
