"""
Compare all 14 bot sessions (13 prior + 1 fresh from 17.11)
Analyze win rates, average streak lengths, pair rates, and step distributions.
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from engine_mirror import PrngDetectorMirror

bot_files = sorted(glob.glob(r'bot\logs\*.jsonl'))
print(f"Found {len(bot_files)} bot log files.")

results = []

for bf in bot_files:
    lines = [json.loads(l) for l in open(bf, encoding='utf-8') if l.strip()]
    if len(lines) < 20: continue
    fn = os.path.basename(bf)
    
    outs = [l['outcome'] for l in lines]
    nz = [x for x in outs if x != 'ZERO']
    
    # Calculate streaks
    streaks = []
    if nz:
        c = nz[0]; cur_len = 1
        for i in range(1, len(nz)):
            if nz[i] == c: cur_len += 1
            else:
                streaks.append((c, cur_len))
                c = nz[i]; cur_len = 1
        streaks.append((c, cur_len))
        
    avg_s_all = sum(l for c, l in streaks) / len(streaks) if streaks else 0
    st_r = [l for c, l in streaks if c == 'RED']
    st_b = [l for c, l in streaks if c == 'BLACK']
    avg_s_r = sum(st_r) / len(st_r) if st_r else 0
    avg_s_b = sum(st_b) / len(st_b) if st_b else 0
    
    # Pairs (len == 2) ratio
    pairs_count = sum(1 for c, l in streaks if l == 2)
    singles_count = sum(1 for c, l in streaks if l == 1)
    deep_count = sum(1 for c, l in streaks if l >= 3)
    tot_st = len(streaks)
    
    # Run v16.0 prediction engine on this session
    v16_wins = 0
    v16_nz_tot = 0
    v16_steps = []
    cur_step = 1
    max_step = 1
    high_steps_count = 0 # steps >= 6
    
    hist = []
    for l in lines:
        rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(hist)
        out = l['outcome']
        
        is_win = (out == rec and out != 'ZERO')
        if out != 'ZERO':
            v16_nz_tot += 1
            if is_win: v16_wins += 1
            
        if is_win:
            v16_steps.append(cur_step)
            cur_step = 1
        else:
            cur_step += 1
            if cur_step > max_step: max_step = cur_step
            if cur_step >= 6: high_steps_count += 1
            if cur_step > 9: cur_step = 1 # reset
            
        hist.append(out)
        
    wr_nz = (v16_wins / v16_nz_tot * 100) if v16_nz_tot else 0
    avg_step = sum(v16_steps) / len(v16_steps) if v16_steps else 0
    
    results.append({
        'fn': fn,
        'spins': len(lines),
        'avg_s': avg_s_all,
        'avg_r': avg_s_r,
        'avg_b': avg_s_b,
        'singles_pct': singles_count / tot_st * 100 if tot_st else 0,
        'pairs_pct': pairs_count / tot_st * 100 if tot_st else 0,
        'deep_pct': deep_count / tot_st * 100 if tot_st else 0,
        'wr_nz': wr_nz,
        'avg_step': avg_step,
        'max_step': max_step,
        'high_steps': high_steps_count
    })

print("\n" + "="*115)
print(f"{'Session File':<32} {'Spins':>6} {'AvgSt':>6} {'AvgR':>6} {'AvgB':>6} {'Singles%':>9} {'Pairs%':>8} {'Deep%':>7} {'v16 WR%':>8} {'AvgStp':>7} {'MaxStp':>7} {'Stp>=6':>7}")
print("="*115)
for r in results:
    is_fresh = ('20261117' in r['fn'])
    prefix = ">>> " if is_fresh else "    "
    print(f"{prefix}{r['fn']:<28} {r['spins']:>6} {r['avg_s']:>6.2f} {r['avg_r']:>6.2f} {r['avg_b']:>6.2f} {r['singles_pct']:>8.1f}% {r['pairs_pct']:>7.1f}% {r['deep_pct']:>6.1f}% {r['wr_nz']:>7.2f}% {r['avg_step']:>7.2f} {r['max_step']:>7} {r['high_steps']:>7}")
