import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from test_high_step_safety import deep_runs

s8 = [r for r in deep_runs if r['max_step'] >= 7]
print(f"Found {len(s8)} sequences reaching Step >= 7:")
for r in s8:
    print('='*70)
    print(f"Session: {r['sess']} | Max Step: {r['max_step']}")
    for step_num, rec, out, state, conf in r['losses']:
        print(f"  Step {step_num}: Rec={rec:<5} (Conf={conf}%, State={state:<24}) | Out={out}")
