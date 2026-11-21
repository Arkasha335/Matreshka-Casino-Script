import glob, json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()

patterns = defaultdict(lambda: {'A': 0, 'B': 0, 'ZERO': 0})

for s in sessions:
    outs = s['outcomes']
    for i in range(4, len(outs)):
        w4 = [x for x in outs[:i] if x != 'ZERO'][-4:]
        if len(w4) == 4:
            first = w4[0]
            norm = ''.join(['A' if x == first else 'B' for x in w4])
            nxt = outs[i]
            if nxt == 'ZERO':
                patterns[norm]['ZERO'] += 1
            elif nxt == first:
                patterns[norm]['A'] += 1
            else:
                patterns[norm]['B'] += 1

print("\n--- Micro-Pattern Continuations (Last 4 Non-Zero Spins) ---")
print(f"{'Pattern':10s} | {'Total':6s} | {'Next A':8s} | {'Next B':8s} | {'Next ZERO':10s} | {'P(A | non-zero)':18s} | {'P(B | non-zero)':18s}")
print("-" * 95)
for pat, d in sorted(patterns.items(), key=lambda x: -(x[1]['A'] + x[1]['B'])):
    tot = d['A'] + d['B'] + d['ZERO']
    nz = d['A'] + d['B']
    p_a = d['A'] / nz * 100 if nz else 0
    p_b = d['B'] / nz * 100 if nz else 0
    print(f"{pat:10s} | {tot:6d} | {d['A']:8d} | {d['B']:8d} | {d['ZERO']:10d} | {p_a:5.2f}%             | {p_b:5.2f}%")
