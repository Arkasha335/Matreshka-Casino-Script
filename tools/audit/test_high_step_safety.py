"""
Investigate High-Step Behavior (Steps >= 4) across all 49 sessions.
Simulate different policy modifications:
1. Baseline v16.0
2. v16.1 with Purified Streak-Mood Neural Net + Calibrated Fallback
3. Anti-Phase Breaker at Step >= 4 (Trend Anchoring vs Alternation Locking)
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, get_cfg_v15_1_2, simulate_session
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

# Let's inspect all losing sequences that reached Step >= 5 in v16.0
deep_runs = []

for s_idx, sess in enumerate(sessions):
    outs = sess['outcomes']
    hist = []
    step = 1
    cdt = 0
    seq_loss_history = []
    
    for t, out in enumerate(outs):
        rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(hist)
        is_win = (out == rec and out != 'ZERO')
        
        if is_win:
            if step >= 5:
                deep_runs.append({
                    'sess': sess['file'],
                    'spin': t,
                    'max_step': step,
                    'cdt': cdt,
                    'losses': list(seq_loss_history),
                    'final_win': out,
                    'closed': True
                })
            step = 1
            cdt = 0
            seq_loss_history = []
        else:
            seq_loss_history.append((step, rec, out, state, conf))
            step += 1
            if step > 10:
                deep_runs.append({
                    'sess': sess['file'],
                    'spin': t,
                    'max_step': 10,
                    'cdt': cdt,
                    'losses': list(seq_loss_history),
                    'closed': False
                })
                step = 1
                cdt = 0
                seq_loss_history = []
                
        hist.append(out)

print(f"\nTotal sequences reaching Step >= 5 in v16.0 across all 49 sessions: {len(deep_runs)}")
step_dist = {}
for r in deep_runs:
    step_dist[r['max_step']] = step_dist.get(r['max_step'], 0) + 1
for st in sorted(step_dist.keys()):
    print(f"  Reached Step {st}: {step_dist[st]} sequences")

print("\n--- Detailed Analysis of Top 5 Deepest Sequences ---")
for r in deep_runs[:5]:
    print(f"\nSession: {r['sess']} | Max Step: {r['max_step']}")
    for step_num, rec, out, state, conf in r['losses']:
        print(f"  Step {step_num}: Rec={rec:<5} (State={state:<22}, Conf={conf}%) | Out={out:<5} -> LOSS")
