import os, sys
sys.path.append(os.path.dirname(__file__))
from research_2_mode_switching import simulate_corpus, sessions

for prof, init_b in [('APEX_IDEAL', 2_000_000), ('APEX_IDEAL', 3_500_000), ('TURBO_HARVEST', 2_000_000)]:
    print(f"\n=== PER-SESSION DETAILS: {prof} | Init={init_b:,} | Policy=CURRENT vs LOCK_ZEBRA ===")
    rc = simulate_corpus(prof, init_b, 'CURRENT')['results']
    rl = simulate_corpus(prof, init_b, 'LOCK_ZEBRA')['results']
    print(f"{'Session':<36} | {'Spins':>5} | {'CURR Net':>11} | {'LOCK Net':>11} | {'C MaxSt':>7} | {'L MaxSt':>7} | {'C DD':>10}")
    print("-" * 105)
    for c, l in zip(rc, rl):
        diff = abs(c['net'] - l['net'])
        if c['max_step'] >= 7 or l['max_step'] >= 7 or c['net'] < 0 or l['net'] < 0 or diff > 30000:
            print(f"{c['name'][:36]:<36} | {c['spins']:>5} | {c['net']:>+11,d} | {l['net']:>+11,d} | {c['max_step']:>7} | {l['max_step']:>7} | {c['dd']:>10,d}")
