import json, glob, os

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json') +
    glob.glob(r'bot\logs\*.jsonl')
)

sessions = []
for p in paths:
    if not os.path.exists(p): continue
    try:
        if p.endswith('.jsonl'):
            lines = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
            outs = [r.get('outcome') or r.get('input_result') for r in lines]
        else:
            d = json.load(open(p, encoding='utf-8'))
            logs = d.get('logs', []) if isinstance(d, dict) else d
            outs = [r.get('outcome') or r.get('input_result') or r.get('actual_outcome') for r in logs]
        outs = [x for x in outs if x in ('RED', 'BLACK', 'ZERO')]
        if len(outs) >= 30:
            sessions.append((os.path.basename(p), outs))
    except Exception:
        pass

print(f"Loaded {len(sessions)} valid sessions.")

# Let's test the alternation hypothesis when L1 != L2 (cas == 1):
# Option A: Current logic (if altRate in 0.60..0.79: followL1=True -> repeat L1; if altRate >= 0.80: continue alt)
# Option B: Pure alternation continuation when altRate >= 0.50 (if altRate >= 0.50, predict continue alternation)
# Option C: Momentum-based alternation

wins_A = 0
wins_B = 0
total_cas1 = 0

for s_name, outs in sessions:
    nz = []
    for o in outs:
        if o != 'ZERO':
            nz.append(o)
            if len(nz) >= 5:
                L1, L2 = nz[-1], nz[-2]
                if L1 != L2:
                    # cas == 1
                    total_cas1 += 1
                    # Next actual outcome
                    pass

print(f"Total sessions: {len(sessions)}")

# Let's test next outcome after L1 != L2:
cas1_evals = 0
opt_A_wins = 0
opt_B_wins = 0 # always continue alternation if altRate >= 0.55
opt_repeat_wins = 0
opt_alt_wins = 0

for s_name, outs in sessions:
    hist_nz = []
    for i in range(len(outs) - 1):
        o = outs[i]
        nxt = outs[i+1]
        if o != 'ZERO':
            hist_nz.append(o)
            if len(hist_nz) >= 4 and nxt != 'ZERO':
                L1, L2 = hist_nz[-1], hist_nz[-2]
                if L1 != L2:
                    cas1_evals += 1
                    # Option Alt: predict opposite of L1
                    pred_alt = 'BLACK' if L1 == 'RED' else 'RED'
                    # Option Repeat: predict L1
                    pred_rep = L1
                    
                    if nxt == pred_alt: opt_alt_wins += 1
                    if nxt == pred_rep: opt_repeat_wins += 1

                    # Current logic in PrngDetector:
                    slice_nz = hist_nz[-6:]
                    alts = sum(1 for k in range(1, len(slice_nz)) if slice_nz[k] != slice_nz[k-1])
                    alt_rate = alts / (len(slice_nz) - 1)
                    if alt_rate >= 0.80:
                        pred_curr = pred_alt
                    else:
                        pred_curr = pred_rep # followL1 = true
                    if nxt == pred_curr: opt_A_wins += 1

                    # Smarter logic: if alt_rate >= 0.55 -> predict pred_alt, else pred_rep
                    pred_smart = pred_alt if alt_rate >= 0.55 else pred_rep
                    if nxt == pred_smart: opt_B_wins += 1

print(f"Evaluated CAS==1 events (non-zero following non-zero alternation): {cas1_evals}")
print(f"  Always Predict Alternation: Wins={opt_alt_wins} ({opt_alt_wins/cas1_evals*100:.2f}%)")
print(f"  Always Predict Repeat (Pair): Wins={opt_repeat_wins} ({opt_repeat_wins/cas1_evals*100:.2f}%)")
print(f"  Current v15 Logic (0.80 threshold): Wins={opt_A_wins} ({opt_A_wins/cas1_evals*100:.2f}%)")
print(f"  Smart Adaptive Logic (0.55 threshold): Wins={opt_B_wins} ({opt_B_wins/cas1_evals*100:.2f}%)")
