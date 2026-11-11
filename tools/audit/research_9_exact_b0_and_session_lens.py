import os, sys, math, random, time
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round
from research_1_reverse_engineering import load_clean_corpus
from research_3_staking_math import clean_calc_bet

real_sessions = load_clean_corpus()

def gen_empirical(n_sess=2000, spins_per_sess=150, seed=9999):
    rng = random.Random(seed)
    return [['ZERO' if (u := rng.random()) < 0.0485 else ('RED' if u < 0.5242 else 'BLACK') for _ in range(spins_per_sess)] for _ in range(n_sess)]

def precompute_full(outcome_lists):
    traces = []
    for outcomes in outcome_lists:
        history = []
        curr_hyst = 'ZEBRA'
        prev_hyst = 'ZEBRA'
        s_danger = 999
        s_curr = 0
        seq = []
        for out in outcomes:
            rec, _, _ = PrngDetectorMirror.get_recommendation_and_confidence(history)
            is_win = (out == rec and out != 'ZERO')
            raw_mode = PrngDetectorMirror.detect_mode(history) if history else 'ZEBRA'
            if history[-10:].count('ZERO') >= 3 and raw_mode == 'ZEBRA':
                raw_mode = 'TRANSITION'
            seq.append((is_win, curr_hyst, raw_mode))
            history.append(out)
            curr_hyst, prev_hyst, s_danger, s_curr = PrngDetectorMirror.detect_mode_with_hysteresis(
                history, prev_hyst, curr_hyst, s_danger, s_curr
            )
        traces.append(seq)
    return traces

def sim_policy(traces, cfg, init_bank=3_500_000, use_no_cd=False):
    n_sess = len(traces)
    wins = 0
    busts = 0
    total_net = 0
    total_spins = 0
    dds = []
    hrs = []
    for seq in traces:
        bank = init_bank
        peak = bank
        sess_dd = 0
        step = 1
        cdt = 0
        prev_bet = None
        busted = False
        for is_win, hyst_mode, raw_mode in seq:
            if bank < 1000:
                busted = True
                break
            mode = raw_mode if use_no_cd else hyst_mode
            if step == 1: prev_bet = None
            b0, t_steps, shape, xmin = cfg[mode]
            bet = clean_calc_bet(cdt, step, b0, t_steps, bank, prev_bet, geom_x_min=xmin, shape=shape)
            total_spins += 1
            if is_win:
                net = js_round(bet * 0.98)
                bank += net
                cdt = max(0, js_round(cdt - net))
                if cdt < 10: cdt = 0
                if cdt == 0: step = 1
            else:
                bank -= bet
                cdt += bet
                step += 1
            prev_bet = bet
            if bank > peak: peak = bank
            dd = peak - bank
            if dd > sess_dd: sess_dd = dd
        sess_net = bank - init_bank
        total_net += sess_net
        if sess_net > 0: wins += 1
        if busted: busts += 1
        dds.append(sess_dd)
        hrs.append(sess_net / len(seq) * 270.0)
    dds.sort()
    hrs.sort()
    return {
        'net': total_net,
        'mean_hr': total_net / max(1, total_spins) * 270.0,
        'med_hr': hrs[len(hrs)//2],
        'p25_hr': hrs[int(0.25 * len(hrs))],
        'win_pct': wins / n_sess * 100.0,
        'bust_pct': busts / n_sess * 100.0,
        'p95_dd': dds[int(0.95 * len(dds))],
        'max_dd': dds[-1],
    }

print("Precomputing 2,000 synthetic sessions for 60, 100, 150 spin horizons + 27 Real...")
raw_150 = gen_empirical(2000, 150, seed=9999)
tr_real = precompute_full([s['outcomes'] for s in real_sessions])
tr_60 = precompute_full([x[:60] for x in raw_150])
tr_100 = precompute_full([x[:100] for x in raw_150])
tr_150 = precompute_full(raw_150)

single_ladder_tests = [
    ("N=10 | B0=1000 High X (2.154x)", {'ZEBRA':(1000,10,'GEOM',2.025), 'TRANSITION':(1000,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("N=10 | B0=1400 Bal  X (2.075x)", {'ZEBRA':(1400,10,'GEOM',2.025), 'TRANSITION':(1400,10,'GEOM',2.025), 'DANGER':(1400,10,'GEOM',2.025)}),
    ("N=10 | B0=1700 Flat X (2.025x)", {'ZEBRA':(1700,10,'FLAT_TBB',2.025), 'TRANSITION':(1700,10,'FLAT_TBB',2.025), 'DANGER':(1700,10,'FLAT_TBB',2.025)}),
    ("N=9  | B0=1000 High X (2.371x)", {'ZEBRA':(1000,9,'GEOM',2.025), 'TRANSITION':(1000,9,'GEOM',2.025), 'DANGER':(1000,9,'GEOM',2.025)}),
    ("N=9  | B0=2000 Bal  X (2.172x)", {'ZEBRA':(2000,9,'GEOM',2.025), 'TRANSITION':(2000,9,'GEOM',2.025), 'DANGER':(2000,9,'GEOM',2.025)}),
    ("N=9  | B0=3000 Opt  X (2.067x)", {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(3000,9,'GEOM',2.025), 'DANGER':(3000,9,'GEOM',2.025)}),
    ("N=9  | B0=3500 Flat X (2.025x)", {'ZEBRA':(3500,9,'FLAT_TBB',2.025), 'TRANSITION':(3500,9,'FLAT_TBB',2.025), 'DANGER':(3500,9,'FLAT_TBB',2.025)}),
    ("N=8  | B0=1000 High X (2.400x)", {'ZEBRA':(1000,8,'GEOM',2.025), 'TRANSITION':(1000,8,'GEOM',2.025), 'DANGER':(1000,8,'GEOM',2.025)}),
    ("N=8  | B0=4000 Opt  X (2.197x)", {'ZEBRA':(4000,8,'GEOM',2.025), 'TRANSITION':(4000,8,'GEOM',2.025), 'DANGER':(4000,8,'GEOM',2.025)}),
]

print("\n=== EFFECT OF (B0 vs X) ACROSS 60 / 100 / 150 SPIN SESSIONS (Init 3.5M, 2,000 MC Sessions) ===")
print(f"{'Ladder':<33} | {'60sp Win%':>9} {'60sp Med/h':>10} {'60sp P25/h':>10} | {'100sp Win%':>10} {'100sp Med/h':>11} | {'150sp Win%':>10} {'150sp Bust%':>11} {'150sp Med/h':>11}")
print("-" * 134)
for label, cfg in single_ladder_tests:
    r60 = sim_policy(tr_60, cfg, 3_500_000, use_no_cd=True)
    r100 = sim_policy(tr_100, cfg, 3_500_000, use_no_cd=True)
    r150 = sim_policy(tr_150, cfg, 3_500_000, use_no_cd=True)
    print(f"{label:<33} | {r60['win_pct']:>8.1f}% {r60['med_hr']:>+10,.0f} {r60['p25_hr']:>+10,.0f} | {r100['win_pct']:>9.1f}% {r100['med_hr']:>+11,.0f} | {r150['win_pct']:>9.1f}% {r150['bust_pct']:>10.2f}% {r150['med_hr']:>+11,.0f}")

print("\n=== LOW & MID BANKROLL TIER AUDIT (Real 27 + 2,000 x 150-spin MC) ===")
bank_tests = [
    (500_000,   "500k N=8 B0=1000 All",                  {'ZEBRA':(1000,8,'GEOM',2.025),  'TRANSITION':(1000,8,'GEOM',2.025),  'DANGER':(1000,8,'GEOM',2.025)}, True),
    (1_000_000, "1M   N=9 B0=1000 All",                  {'ZEBRA':(1000,9,'GEOM',2.025),  'TRANSITION':(1000,9,'GEOM',2.025),  'DANGER':(1000,9,'GEOM',2.025)}, True),
    (1_000_000, "1M   N=10 B0=1000 All (v12.4 current)", {'ZEBRA':(1000,10,'GEOM',2.025), 'TRANSITION':(1000,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, False),
    (1_000_000, "1M   Z=1500/N8 T=1000/N9 D=1000/N9",    {'ZEBRA':(1500,8,'GEOM',2.025),  'TRANSITION':(1000,9,'GEOM',2.025),  'DANGER':(1000,9,'GEOM',2.025)}, True),
    (2_000_000, "2M   Z2000/N9 T1200/N10 D1000/N10 HYST",{'ZEBRA':(2000,9,'GEOM',2.025),  'TRANSITION':(1200,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, False),
    (2_000_000, "2M   Z2000/N9 T1200/N10 D1000/N10 NOCD",{'ZEBRA':(2000,9,'GEOM',2.025),  'TRANSITION':(1200,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, True),
    (2_000_000, "2M   Z1700/N10 T1300/N10 D1000/N10",    {'ZEBRA':(1700,10,'GEOM',2.025), 'TRANSITION':(1300,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, True),
    (2_000_000, "2M   Z1500/N10 T1200/N10 D1000/N10",    {'ZEBRA':(1500,10,'GEOM',2.025), 'TRANSITION':(1200,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, True),
    (2_000_000, "2M   Z1000/N10 All GEOM",               {'ZEBRA':(1000,10,'GEOM',2.025), 'TRANSITION':(1000,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, True),
]
print(f"{'Bankroll / Config':<44} | {'Real Win':>8} | {'Real MaxDD':>10} | {'MC Win%':>7} | {'MC Bust%':>8} | {'MC Med/hr':>10} | {'MC Mean/hr':>11}")
print("-" * 116)
for b_init, label, cfg, ncd in bank_tests:
    rr = sim_policy(tr_real, cfg, b_init, use_no_cd=ncd)
    rm = sim_policy(tr_150, cfg, b_init, use_no_cd=ncd)
    print(f"{label:<44} | {rr['win_pct']:>6.1f}%  | {rr['max_dd']:>10,d} | {rm['win_pct']:>6.1f}% | {rm['bust_pct']:>7.2f}% | {rm['med_hr']:>+10,.0f} | {rm['mean_hr']:>+11,.0f}")
