import os, sys, math, random, json, glob, hashlib
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round

def load_clean():
    paths = sorted(
        glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
        [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
        glob.glob(r'D:\Downloads\matreshka*.json') +
        glob.glob(r'D:\Downloads\quantum*.json')
    )
    skip = {'matreshka_session_2026-03-31.json', 'matreshka_session_2026-04-01 (3).json',
            'matreshka_session_2026-03-31 (1).json', 'matreshka_session_2026-03-31 (2).json', 'matreshka_session_2026-03-31 (3).json'}
    res, seen = [], set()
    for p in paths:
        if not os.path.exists(p): continue
        fn = os.path.basename(p)
        if fn in skip: continue
        with open(p, 'r', encoding='utf-8') as f: d = json.load(f)
        logs = d.get('logs', []) if isinstance(d, dict) else d
        if fn == 'matreshka_quantum_v11_2026-11-08.json': logs = logs[:22]
        outs = [e.get('input_result') or e.get('actual_outcome') or e.get('outcome') for e in logs]
        outs = [x for x in outs if x in ('RED', 'BLACK', 'ZERO')]
        h = hashlib.md5(','.join(outs).encode()).hexdigest()
        if outs and h not in seen:
            seen.add(h); res.append((fn, outs))
    return res

def gen_empirical(n_sess=2000, spins_per_sess=100, seed=2026):
    rng = random.Random(seed)
    return [['ZERO' if (u := rng.random()) < 0.0485 else ('RED' if u < 0.5242 else 'BLACK') for _ in range(spins_per_sess)] for _ in range(n_sess)]

def precompute_full(outcome_lists):
    traces = []
    for outs in outcome_lists:
        history = []; curr_h = 'ZEBRA'; prev_h = 'ZEBRA'; sd = 999; sc = 0; seq = []
        for out in outs:
            rec, _, _ = PrngDetectorMirror.get_recommendation_and_confidence(history)
            is_win = (out == rec and out != 'ZERO')
            raw = PrngDetectorMirror.detect_mode(history) if history else 'ZEBRA'
            if history[-10:].count('ZERO') >= 3 and raw == 'ZEBRA': raw = 'TRANSITION'
            seq.append((is_win, curr_h, raw))
            history.append(out)
            curr_h, prev_h, sd, sc = PrngDetectorMirror.detect_mode_with_hysteresis(history, prev_h, curr_h, sd, sc)
        traces.append(seq)
    return traces

def dynamic_terminal_bet(cdt, step, base_bet, target_steps, bankroll, table_limit, prev_bet, use_terminal_snap=True, guard_strict=True):
    """
    Universal Mathematical Staking Engine for ANY TableLimit (1M or 2M) & ANY Bankroll:
    - Cycle budget = bankroll + cdt.
    - Max sustainable terminal bet so sum of steps ~ cycle_budget: roughly cycle_budget / 1.92 (or direct solve).
    - Step N lands squarely on terminal_cap (maximizing recovery profit if won on Step N or penultimate steps!),
      WITHOUT exceeding table_limit or wallet!
    - Horizon Guard generalizes from 980k (at 1M limit) to (0.98 * terminal_cap - safety_margin) for ANY table_limit!
    """
    base_bet = max(1000, base_bet)
    if cdt <= 0 or step <= 1:
        return min(base_bet, max(1000, bankroll), table_limit)

    cycle_cap = bankroll + cdt
    # Exact geometric reserve divisor for X in [2.04..2.20] is ~1.88-1.95
    affordable_terminal = math.floor(cycle_cap / 1.92)
    terminal_cap = max(1000, min(table_limit, affordable_terminal))

    rem = max(1, target_steps - step + 1)
    min_tbb = math.ceil((cdt + base_bet) / 0.98)

    if rem == 1:
        if use_terminal_snap:
            # User explicitly wants last bet to push up to tableLimit/affordable ceiling (as long as wallet covers it)
            # UNLESS CDT is tiny partial recovery (< 25% of terminal_cap), in which case cap nicely at max(min_tbb, ...)
            bet = min(terminal_cap, bankroll, table_limit)
            if cdt < terminal_cap * 0.35:
                bet = min(bet, min_tbb)
        else:
            bet = min(min_tbb, terminal_cap, bankroll, table_limit)
        return max(1000, js_round(bet))

    pb = prev_bet if (prev_bet is not None and prev_bet > 0) else base_bet
    ratio = terminal_cap / max(1, pb)
    # Dynamically solve multiplier X so that remaining steps span from prev_b cleanly up to terminal_cap!
    dyn_x = max(2.025, min(2.60, math.pow(ratio, 1.0 / rem)))
    geom_bet = js_round(pb * dyn_x)
    bet = max(min_tbb, geom_bet)

    # Universal Horizon Guard on penultimate step (rem == 2):
    # Ensure CDT after losing step N-1 allows terminal step N (at terminal_cap) to still recover in positive profit!
    if guard_strict and rem == 2:
        max_penult = math.floor(terminal_cap * 0.98) - cdt - 100
        min_breakeven_penult = math.ceil((cdt + 100) / 0.98)
        if max_penult >= min_breakeven_penult:
            bet = min(bet, max_penult)

    return js_round(max(1000, min(bet, table_limit, bankroll)))

real_raw = load_clean()
tr_real = precompute_full([x[1] for x in real_raw])
tr_mc100 = precompute_full(gen_empirical(2000, 100, 2026)) # 100-spin ~22 min realistic sessions

def eval_config(traces, cfg, init_bank, table_limit, no_cd=True, zebra_lock=False, seq_step_lock=True):
    wins = busts = total_net = total_spins = 0
    hrs, dds = [], []
    for seq in traces:
        bank = init_bank; peak = bank; sess_dd = 0
        step = 1; cdt = 0; prev_bet = None; seq_start = 'ZEBRA'; seq_n = None; busted = False
        for is_win, hyst_m, raw_m in seq:
            if bank < 1000: busted = True; break
            active_m = raw_m if no_cd else hyst_m
            if step == 1:
                seq_start = active_m
                prev_bet = None
                seq_n = cfg[active_m][1]
            bm = 'ZEBRA' if (zebra_lock and seq_start == 'ZEBRA') else active_m
            b0, n_mode = cfg[bm]
            # Consistent sequence step capacity: if started with higher B0 (fewer steps N), don't inflate N mid-series
            eff_n = min(seq_n, n_mode) if (seq_step_lock and seq_n is not None) else n_mode

            bet = dynamic_terminal_bet(cdt, step, b0, eff_n, bank, table_limit, prev_bet)
            total_spins += 1
            if is_win:
                net = js_round(bet * 0.98); bank += net; cdt = max(0, js_round(cdt - net))
                if cdt < 10: cdt = 0
                if cdt == 0: step = 1
            else:
                bank -= bet; cdt += bet; step += 1
            prev_bet = bet
            if bank > peak: peak = bank
            sess_dd = max(sess_dd, peak - bank)
        net_s = bank - init_bank
        total_net += net_s
        if net_s > 0: wins += 1
        if busted: busts += 1
        dds.append(sess_dd)
        hrs.append(net_s / len(seq) * 270.0)
    hrs.sort(); dds.sort()
    n = len(traces)
    return {
        'win': wins/n*100, 'bust': busts/n*100,
        'med': hrs[n//2], 'p75': hrs[int(0.75*n)], 'p90': hrs[int(0.90*n)],
        'mean': total_net/max(1,total_spins)*270.0, 'max_dd': dds[-1]
    }

print("\n==============================================================================================================================")
print("PART 1: MAX TABLE LIMIT = 1,000,000 RUB (Standard CRMP Limit) | Comparing Step Horizons & Aggressive Yield")
print("Bankroll: 3,800,000 RUB & 6,500,000 RUB | Sessions: Real 27 & 2,000 x 100-spin (~22 min) MC")
print("==============================================================================================================================")
configs_1m = [
    ("N=10 Shield (Z1700/10 T1300/10 D1000/10)",     {'ZEBRA':(1700,10), 'TRANSITION':(1300,10), 'DANGER':(1000,10)}, False, False),
    ("N=9/10 Apex Old (Z3000/9 T1500/10 D1000/10)",  {'ZEBRA':(3000,9),  'TRANSITION':(1500,10), 'DANGER':(1000,10)}, True,  False),
    ("N=9 Pure High-X (Z2500/9 T2000/9 D1500/9)",    {'ZEBRA':(2500,9),  'TRANSITION':(2000,9),  'DANGER':(1500,9)},  True,  True),
    ("N=9 Max-Base    (Z3500/9 T2500/9 D1500/9)",    {'ZEBRA':(3500,9),  'TRANSITION':(2500,9),  'DANGER':(1500,9)},  True,  True),
    ("N=8/9 Blend     (Z5000/8 T3000/9 D1500/9)",    {'ZEBRA':(5000,8),  'TRANSITION':(3000,9),  'DANGER':(1500,9)},  True,  True),
    ("N=8 All-In Opt  (Z5000/8 T3500/8 D2000/8)",    {'ZEBRA':(5000,8),  'TRANSITION':(3500,8),  'DANGER':(2000,8)},  True,  True),
    ("N=8 High-Yield  (Z6500/8 T4500/8 D2500/8)",    {'ZEBRA':(6500,8),  'TRANSITION':(4500,8),  'DANGER':(2500,8)},  True,  True),
    ("N=7 Extreme     (Z10000/7 T7000/7 D4000/7)",   {'ZEBRA':(10000,7), 'TRANSITION':(7000,7),  'DANGER':(4000,7)},  True,  True),
]
print(f"{'Config (M = 1M, Init 3.8M)':<44} | {'R27 Win':>7} {'R27 Med/h':>10} {'R27 P90/h':>10} {'R27 DD':>9} | {'MC100 Win':>9} {'MC Bust':>7} {'MC Med/h':>10} {'MC P75/h':>10}")
print("-" * 130)
for lbl, cfg, ncd, zl in configs_1m:
    rr = eval_config(tr_real, cfg, 3_800_000, 1_000_000, ncd, zl)
    rm = eval_config(tr_mc100, cfg, 3_800_000, 1_000_000, ncd, zl)
    print(f"{lbl:<44} | {rr['win']:>6.1f}% {rr['med']:>+10,.0f} {rr['p90']:>+10,.0f} {rr['max_dd']:>9,d} | {rm['win']:>8.1f}% {rm['bust']:>6.2f}% {rm['med']:>+10,.0f} {rm['p75']:>+10,.0f}")

print("\n==============================================================================================================================")
print("PART 2: MAX TABLE LIMIT = 2,000,000 RUB (If Limit is 2M or Cycle Ceiling = 2M Bet)")
print("Bankroll: 4,000,000 RUB & 6,500,000 RUB (Necessary because 10-step up to 2M bet costs ~3.73M RUB!)")
print("==============================================================================================================================")
configs_2m = [
    ("M=2M N=10 UltraSafe (Z3500/10 T2500/10 D2000/10)", {'ZEBRA':(3500,10), 'TRANSITION':(2500,10), 'DANGER':(2000,10)}, True,  False),
    ("M=2M N=10 High-X    (Z2000/10 T2000/10 D1000/10)", {'ZEBRA':(2000,10), 'TRANSITION':(2000,10), 'DANGER':(1000,10)}, True,  True),
    ("M=2M N=9/10 Apex    (Z6000/9  T3000/10 D2000/10)", {'ZEBRA':(6000,9),  'TRANSITION':(3000,10), 'DANGER':(2000,10)}, True,  True),
    ("M=2M N=9 High-EV    (Z6500/9  T4500/9  D2500/9)",  {'ZEBRA':(6500,9),  'TRANSITION':(4500,9),  'DANGER':(2500,9)},  True,  True),
    ("M=2M N=8 Aggressive (Z12000/8 T8000/8  D4000/8)",  {'ZEBRA':(12000,8), 'TRANSITION':(8000,8),  'DANGER':(4000,8)},  True,  True),
]
for bank_test in [4_000_000, 6_500_000]:
    print(f"\n--- Init Bankroll = {bank_test:,} RUB (Table Limit M = 2,000,000) ---")
    print(f"{'Config (M = 2M)':<50} | {'R27 Win':>7} {'R27 Med/h':>10} {'R27 P90/h':>10} {'R27 DD':>9} | {'MC100 Win':>9} {'MC Bust':>7} {'MC Med/h':>10} {'MC P75/h':>10}")
    print("-" * 136)
    for lbl, cfg, ncd, zl in configs_2m:
        rr = eval_config(tr_real, cfg, bank_test, 2_000_000, ncd, zl)
        rm = eval_config(tr_mc100, cfg, bank_test, 2_000_000, ncd, zl)
        print(f"{lbl:<50} | {rr['win']:>6.1f}% {rr['med']:>+10,.0f} {rr['p90']:>+10,.0f} {rr['max_dd']:>9,d} | {rm['win']:>8.1f}% {rm['bust']:>6.2f}% {rm['med']:>+10,.0f} {rm['p75']:>+10,.0f}")
