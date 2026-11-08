import json
import glob

files = glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json')
files.append(r'd:\Downloads\matreshka_quantum_v11_2026-11-08.json')
files.append(r'd:\Downloads\matreshka_session_2026-11-08.json')

all_sessions_spins = []
for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    logs = data.get('logs', [])
    outcomes = []
    for entry in logs:
        res = entry.get('input_result') or entry.get('actual_outcome')
        if res:
            outcomes.append(res)
    all_sessions_spins.append(outcomes)

# Conditional continuation probability after streak of length k
max_k = 8
for k in range(1, max_k + 1):
    continue_count = 0
    break_count = 0
    zero_count = 0
    for spins in all_sessions_spins:
        for i in range(len(spins) - k):
            window = spins[i:i+k]
            # Check if all k are same color (RED or BLACK)
            if all(x == window[0] and x in ('RED', 'BLACK') for x in window):
                # Check if preceding spin was different (so this is exactly streak of length >= k)
                # Actually, any streak of length at least k:
                next_spin = spins[i+k]
                if next_spin == window[0]:
                    continue_count += 1
                elif next_spin == 'ZERO':
                    zero_count += 1
                else:
                    break_count += 1
    total = continue_count + break_count + zero_count
    if total > 0:
        p_cont = continue_count / (continue_count + break_count) * 100
        p_break = break_count / (continue_count + break_count) * 100
        p_zero = zero_count / total * 100
        print(f"After streak of {k:2d}: Continue={continue_count:3d} ({p_cont:5.1f}%), Break={break_count:3d} ({p_break:5.1f}%), Zero={zero_count:2d} ({p_zero:4.1f}%) [Total={total}]")
