import os, json, glob, math, hashlib
from collections import Counter, defaultdict
import sys
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror

def load_clean_corpus():
    paths = sorted(
        glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
        [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
        glob.glob(r'D:\Downloads\matreshka*.json') +
        glob.glob(r'D:\Downloads\quantum*.json')
    )
    skip_exact = {
        'matreshka_session_2026-03-31.json',      # fast-click UI test (0.4s/spin, 23% Zero)
        'matreshka_session_2026-04-01 (3).json',  # fast-click UI test (0.8s/spin, 11% Zero)
        # Incremental prefix snapshots (strictly contained in matreshka_session_2026-03-31 (4).json):
        'matreshka_session_2026-03-31 (1).json',
        'matreshka_session_2026-03-31 (2).json',
        'matreshka_session_2026-03-31 (3).json',
    }
    sessions = []
    seen = set()
    for p in paths:
        if not os.path.exists(p): continue
        fname = os.path.basename(p)
        if fname in skip_exact: continue
        with open(p, 'r', encoding='utf-8') as f:
            d = json.load(f)
        logs = d.get('logs', []) if isinstance(d, dict) else d
        # Special truncation for v11_2026-11-08: freeze-click manual tail after index 21
        if fname == 'matreshka_quantum_v11_2026-11-08.json':
            logs = logs[:22]
        outcomes = []
        dts = []
        for i, e in enumerate(logs):
            res = e.get('input_result') or e.get('actual_outcome') or e.get('outcome')
            if res in ('RED', 'BLACK', 'ZERO'):
                outcomes.append(res)
                dt = e.get('time_since_last_spin')
                if dt is None and i > 0 and 'timestamp' in e and 'timestamp' in logs[i-1]:
                    dt = e['timestamp'] - logs[i-1]['timestamp']
                if dt is not None and 2000 <= dt <= 120000:
                    dts.append(dt / 1000.0)
        h = hashlib.md5(','.join(outcomes).encode()).hexdigest()
        if outcomes and h not in seen:
            seen.add(h)
            sessions.append({'name': fname, 'path': p, 'outcomes': outcomes, 'dts': dts})
    return sessions

sessions = load_clean_corpus()
total_spins = sum(len(s['outcomes']) for s in sessions)
all_dts = [dt for s in sessions for dt in s['dts']]
avg_dt = sum(all_dts) / len(all_dts)
med_dt = sorted(all_dts)[len(all_dts)//2]

print(f"=== CLEAN LIVE CORPUS SUMMARY ===")
print(f"Unique Clean Live Sessions: {len(sessions)}")
print(f"Total Clean Live Spins:     {total_spins}")
print(f"Spin Cadence (valid 2-120s gaps, n={len(all_dts)}): Mean = {avg_dt:.2f}s ({3600/avg_dt:.0f} spins/hr) | Median = {med_dt:.2f}s ({3600/med_dt:.0f} spins/hr)")

# 1. Color distribution & Zero statistics
all_outcomes = [o for s in sessions for o in s['outcomes']]
r_cnt = all_outcomes.count('RED')
b_cnt = all_outcomes.count('BLACK')
z_cnt = all_outcomes.count('ZERO')
print(f"\n=== 1. COLOR & ZERO DISTRIBUTION (Theory: 48% R / 48% B / 4% Z) ===")
print(f"RED:   {r_cnt:4d} ({r_cnt/total_spins*100:.2f}%)")
print(f"BLACK: {b_cnt:4d} ({b_cnt/total_spins*100:.2f}%)")
print(f"ZERO:  {z_cnt:4d} ({z_cnt/total_spins*100:.2f}%)")

# Test Zero clustering & back-to-back zero
z_after_z = 0
z_prev_total = 0
z_gaps = []
for s in sessions:
    last_z = None
    for idx, o in enumerate(s['outcomes']):
        if idx > 0 and s['outcomes'][idx-1] == 'ZERO':
            z_prev_total += 1
            if o == 'ZERO': z_after_z += 1
        if o == 'ZERO':
            if last_z is not None:
                z_gaps.append(idx - last_z)
            last_z = idx

mean_gap = sum(z_gaps)/len(z_gaps) if z_gaps else 0
var_gap = sum((g - mean_gap)**2 for g in z_gaps)/len(z_gaps) if z_gaps else 0
print(f"P(ZERO after ZERO): {z_after_z}/{z_prev_total} = {z_after_z/max(1,z_prev_total)*100:.2f}% (i.i.d. theory: 4.00%)")
print(f"Inter-Zero Gap: mean={mean_gap:.2f}, std={math.sqrt(var_gap):.2f} (Geometric p=0.04 theory: mean=25.0, std=24.49)")

# 2. Streak distribution & Alternation test vs Bernoulli(0.5 on non-zero)
non_zero_runs = Counter()
total_nz_pairs = 0
nz_same_color = 0
nz_diff_color = 0
for s in sessions:
    nz = [x for x in s['outcomes'] if x != 'ZERO']
    if not nz: continue
    run = 1
    for i in range(1, len(nz)):
        total_nz_pairs += 1
        if nz[i] == nz[i-1]:
            nz_same_color += 1
            run += 1
        else:
            nz_diff_color += 1
            non_zero_runs[run] += 1
            run = 1
    non_zero_runs[run] += 1

total_runs = sum(non_zero_runs.values())
print(f"\n=== 2. STREAK & ALTERNATION TEST (Conditioned on non-ZERO) ===")
print(f"Same-color transition P(X_t == X_{{t-1}}): {nz_same_color}/{total_nz_pairs} = {nz_same_color/total_nz_pairs*100:.2f}% (Pure fair RNG: 50.00%)")
print(f"Alternation rate      P(X_t != X_{{t-1}}): {nz_diff_color}/{total_nz_pairs} = {nz_diff_color/total_nz_pairs*100:.2f}%")
print(f"Std Error around 50% (n={total_nz_pairs}): +/- {0.5/math.sqrt(total_nz_pairs)*100:.2f}% -> Z-score = {(nz_same_color/total_nz_pairs - 0.5)/(0.5/math.sqrt(total_nz_pairs)):+.2f}")

print(f"\nRun-length Distribution (Non-Zero runs, total runs={total_runs}) vs Fair RNG (0.5^L):")
print(f"{'Len':>3} | {'Observed':>8} | {'Expected':>8} | {'Obs %':>7} | {'Exp %':>7} | {'Ratio'}")
for L in range(1, max(non_zero_runs.keys()) + 1):
    obs = non_zero_runs[L]
    exp = total_runs * (0.5 ** L)
    print(f"{L:>3} | {obs:>8d} | {exp:>8.1f} | {obs/total_runs*100:>6.2f}% | {(0.5**L)*100:>6.2f}% | {obs/exp if exp>0 else 0:.2f}x")

# 3. Autocorrelation of alternation in windows (variance of 10-spin alternation rate -> tests regime switching!)
win10_alts = []
win10_z = []
for s in sessions:
    nz = [x for x in s['outcomes'] if x != 'ZERO']
    for i in range(0, len(nz) - 10 + 1, 10):
        chunk = nz[i:i+10]
        alts = sum(1 for j in range(1, 10) if chunk[j] != chunk[j-1]) / 9.0
        win10_alts.append(alts)
    for i in range(0, len(s['outcomes']) - 20 + 1, 20):
        chunk = s['outcomes'][i:i+20]
        win10_z.append(chunk.count('ZERO'))

mean_w = sum(win10_alts)/len(win10_alts)
var_w = sum((x - mean_w)**2 for x in win10_alts)/len(win10_alts)
# Under i.i.d., sum of 9 independent Bernoulli(0.5) / 9 has variance 0.25/9 = 0.02778
theory_var_w = 0.25 / 9.0
print(f"\nRegime Switching Check (10-spin non-overlapping blocks, n={len(win10_alts)} blocks):")
print(f"  Mean alternation rate: {mean_w*100:.2f}% | Observed Variance: {var_w:.5f} vs i.i.d. Theory: {theory_var_w:.5f} (Ratio: {var_w/theory_var_w:.2f}x)")
# Also check lag-1 autocorrelation of alternation indicators?
# Check session-level skew heterogeneity (variance across sessions)
sess_alt = []
for s in sessions:
    if len(s['outcomes']) >= 30:
        nz = [x for x in s['outcomes'] if x != 'ZERO']
        alt = sum(1 for i in range(1, len(nz)) if nz[i] != nz[i-1]) / (len(nz)-1)
        sess_alt.append((s['name'], len(s['outcomes']), alt*100, s['outcomes'].count('RED')/max(1,len(nz))*100, s['outcomes'].count('ZERO')/len(s['outcomes'])*100))

# 4. Full PrngDetector Evaluation by Mode, State, and Sequence Step!
mode_stats = defaultdict(lambda: {'spins': 0, 'wins': 0, 'zero_losses': 0})
state_stats = defaultdict(lambda: {'spins': 0, 'wins': 0})
mode_state_stats = defaultdict(lambda: {'spins': 0, 'wins': 0})
seq_by_start_mode = defaultdict(lambda: {'total_seqs': 0, 'won_in_same': 0, 'switched': 0, 'steps': Counter(), 'max_step': 0})
step_cond_stats = defaultdict(lambda: defaultdict(lambda: [0, 0])) # [start_mode][step] -> [reached, won]
current_mode_step_stats = defaultdict(lambda: defaultdict(lambda: [0, 0])) # [curr_mode][step] -> [reached, won]

for s in sessions:
    history = []
    curr_mode = 'ZEBRA'
    prev_mode = 'ZEBRA'
    s_danger = 999
    s_curr = 0
    step = 1
    seq_start_mode = curr_mode

    for outcome in s['outcomes']:
        if step == 1:
            seq_start_mode = curr_mode
        rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(history)
        is_win = (outcome == rec and outcome != 'ZERO')

        mode_stats[curr_mode]['spins'] += 1
        state_stats[state]['spins'] += 1
        mode_state_stats[(curr_mode, state)]['spins'] += 1
        step_cond_stats[seq_start_mode][step][0] += 1
        current_mode_step_stats[curr_mode][step][0] += 1

        if outcome == 'ZERO':
            mode_stats[curr_mode]['zero_losses'] += 1

        if is_win:
            mode_stats[curr_mode]['wins'] += 1
            state_stats[state]['wins'] += 1
            mode_state_stats[(curr_mode, state)]['wins'] += 1
            step_cond_stats[seq_start_mode][step][1] += 1
            current_mode_step_stats[curr_mode][step][1] += 1

            seq_by_start_mode[seq_start_mode]['total_seqs'] += 1
            seq_by_start_mode[seq_start_mode]['steps'][step] += 1
            seq_by_start_mode[seq_start_mode]['max_step'] = max(seq_by_start_mode[seq_start_mode]['max_step'], step)
            if curr_mode == seq_start_mode:
                seq_by_start_mode[seq_start_mode]['won_in_same'] += 1
            else:
                seq_by_start_mode[seq_start_mode]['switched'] += 1
            step = 1
        else:
            step += 1

        history.append(outcome)
        curr_mode, prev_mode, s_danger, s_curr = PrngDetectorMirror.detect_mode_with_hysteresis(
            history, prev_mode, curr_mode, s_danger, s_curr
        )

print(f"\n=== 3. CURRENT PRNG DETECTOR WINRATES BY MODE (Baseline = 48.00%) ===")
tot_sp = sum(v['spins'] for v in mode_stats.values())
tot_wn = sum(v['wins'] for v in mode_stats.values())
print(f"OVERALL ALL SPINS: {tot_wn}/{tot_sp} = {tot_wn/tot_sp*100:.2f}% (Net edge over 48.00%: {tot_wn/tot_sp*100 - 48:+.2f}%)")
for m in ['ZEBRA', 'TRANSITION', 'DANGER']:
    v = mode_stats[m]
    wr = v['wins']/max(1, v['spins'])*100
    print(f"  {m:<11}: {v['wins']:4d}/{v['spins']:4d} = {wr:5.2f}% (Share: {v['spins']/tot_sp*100:4.1f}% | Zeros: {v['zero_losses']})")

print(f"\n=== 4. WINRATES BY SIGNAL STATE ===")
for st, v in sorted(state_stats.items(), key=lambda x: -x[1]['spins']):
    wr = v['wins']/v['spins']*100
    print(f"  {st:<26}: {v['wins']:4d}/{v['spins']:4d} = {wr:5.2f}%")

print(f"\n=== 5. EMPIRICAL STEP REACH & RECOVERY BY STARTING MODE ===")
for m in ['ZEBRA', 'TRANSITION', 'DANGER']:
    d = seq_by_start_mode[m]
    print(f"\nSequences STARTED in {m} (completed={d['total_seqs']}, max_step={d['max_step']}):")
    print(f"  Completed in same mode: {d['won_in_same']} ({d['won_in_same']/max(1,d['total_seqs'])*100:.1f}%) | Switched mode mid-seq: {d['switched']} ({d['switched']/max(1,d['total_seqs'])*100:.1f}%)")
    print(f"  {'Step':>4} | {'Reached':>7} | {'Won':>5} | {'Cond WR':>8} | {'Cum Solved %':>12}")
    cum_w = 0
    tot_r1 = step_cond_stats[m][1][0]
    for k in range(1, 13):
        r, w = step_cond_stats[m][k]
        if r == 0: continue
        cum_w += w
        print(f"  {k:>4} | {r:>7d} | {w:>5d} | {w/r*100:>7.2f}% | {cum_w/tot_r1*100:>11.2f}%")
