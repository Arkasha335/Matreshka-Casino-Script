import json
import glob
import os

files = glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json')
files.append(r'd:\Downloads\matreshka_quantum_v11_2026-11-08.json')
files.append(r'd:\Downloads\matreshka_session_2026-11-08.json')

all_runs = []
all_spins = []

for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    logs = data.get('logs', [])
    outcomes = []
    for entry in logs:
        res = entry.get('input_result') or entry.get('actual_outcome')
        if res:
            outcomes.append(res)
    all_spins.extend(outcomes)
    
    # Run lengths
    cur_color = None
    cur_len = 0
    for o in outcomes:
        if o in ('RED', 'BLACK'):
            if o == cur_color:
                cur_len += 1
            else:
                if cur_len > 0:
                    all_runs.append((cur_color, cur_len))
                cur_color = o
                cur_len = 1
        else: # ZERO
            if cur_len > 0:
                all_runs.append((cur_color, cur_len))
            cur_color = None
            cur_len = 0
            all_runs.append(('ZERO', 1))
    if cur_len > 0:
        all_runs.append((cur_color, cur_len))

print(f"Total spins analyzed: {len(all_spins)}")
print(f"Total runs: {len(all_runs)}")

from collections import Counter
run_lens = [l for c, l in all_runs if c in ('RED', 'BLACK')]
cnt = Counter(run_lens)
print("\nObserved Run Lengths Distribution vs Theoretical Geometric (p=0.486):")
total_runs_rb = len(run_lens)
for length in sorted(cnt.keys()):
    observed = cnt[length]
    obs_pct = observed / total_runs_rb * 100
    # In independent Bernoulli trials with p=0.5 (or 18/38=0.4737 for specific, or alternating probability)
    # The probability of a run having length k given a run has started is (1 - p_cont) * p_cont^(k-1)
    # where p_cont ~ 18/38 / (36/38) = 0.5
    theo_pct = (0.5 ** length) / 0.5 * 100 # = 0.5^(k-1) * 50%
    print(f"Length {length:2d}: count = {observed:3d} ({obs_pct:5.2f}%) | Theo (p=0.5): {theo_pct:5.2f}%")
