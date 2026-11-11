import os, sys, math, random, time
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round
from research_1_reverse_engineering import load_clean_corpus
from research_3_staking_math import clean_calc_bet
from research_5_monte_carlo_750k import gen_empirical_iid_sessions, gen_adversarial_regime_sessions

real_sessions = load_clean_corpus()

def precompute_full(outcome_lists):
    """Precomputes (is_win, hyst_mode, raw_mode, zero10) accurately."""
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

print("Precomputing 27 Real + 3000 Suite A + 2000 Suite B...")
t0 = time.time()
tr_real = precompute_full([s['outcomes'] for s in real_sessions])
tr_A = precompute_full(gen_empirical_iid_sessions(3000, 150, 2026))
tr_B = precompute_full(gen_adversarial_regime_sessions(2000, 150, 7777))
print(f"Ready in {time.time()-t0:.2f}s.")

def sim_policy(traces, cfg, init_bank=3_500_000, use_no_cd=False, zebra_lock_max_step=0, fast_step1_exit=False, reset_step=None):
    """
    Clean isolated policy tester:
    - use_no_cd: True -> raw_mode without 3+5 spin cooldown trap; False -> current hysteresis
    - fast_step1_exit: keep 3-spin hold ONLY during losing streak (step > 1); on win (step == 1), allow raw_mode directly!
    - zebra_lock_max_step: 0 = no lock, 99 = full lock until win, 4/5 = soft lock up to step K
    """
    n_sess = len(traces)
    wins = 0
    big_losses = 0
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
        seq_start_mode = 'ZEBRA'
        prev_bet = None
        busted = False

        for is_win, hyst_mode, raw_mode in seq:
            if bank < 1000:
                busted = True
                break

            if use_no_cd:
                base_mode = raw_mode
            elif fast_step1_exit and step == 1:
                base_mode = raw_mode
            else:
                base_mode = hyst_mode

            if step == 1:
                seq_start_mode = base_mode
                prev_bet = None

            if reset_step and step > reset_step:
                cdt = 0
                step = 1
                prev_bet = None
                seq_start_mode = base_mode

            if zebra_lock_max_step > 0 and seq_start_mode == 'ZEBRA' and step <= zebra_lock_max_step:
                bet_mode = 'ZEBRA'
            else:
                bet_mode = base_mode

            b0, t_steps, shape, xmin = cfg[bet_mode]
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
        if sess_net <= -500_000: big_losses += 1
        if busted: busts += 1
        dds.append(sess_dd)
        hrs.append(sess_net / len(seq) * 270.0)

    dds.sort()
    hrs.sort()
    mean_hr = total_net / max(1, total_spins) * 270.0
    med_hr = hrs[len(hrs)//2]
    bust_pct = busts / n_sess * 100.0
    return {
        'net': total_net,
        'mean_hr': mean_hr,
        'med_hr': med_hr,
        'win_pct': wins / n_sess * 100.0,
        'big_loss_pct': big_losses / n_sess * 100.0,
        'bust_pct': bust_pct,
        'eff': med_hr / max(0.1, bust_pct),
        'p95_dd': dds[int(0.95 * len(dds))],
        'max_dd': dds[-1],
    }

# PART 1: Clean 2x2x2 Factorial Isolation of NO_COOLDOWN vs ZEBRA_LOCK!
cfg_base = {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}
cfg_base_2m = {'ZEBRA':(2000,9,'GEOM',2.025), 'TRANSITION':(1200,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}

factorial_variants = [
    ("A0: CURRENT (Hysteresis ON, Lock OFF)",       False, 0,  False),
    ("A1: FAST_WIN_EXIT (No cooldown after win)",   False, 0,  True),
    ("A2: RAW_NO_COOLDOWN (Always raw mode)",       True,  0,  False),
    ("B1: CURRENT + ZEBRA_LOCK (until win)",        False, 99, False),
    ("B2: CURRENT + SOFT_ZEBRA_LOCK (steps 1-4)",   False, 4,  False),
    ("B3: CURRENT + SOFT_ZEBRA_LOCK (steps 1-5)",   False, 5,  False),
    ("C1: FAST_WIN_EXIT + ZEBRA_LOCK",              False, 99, True),
    ("C2: RAW_NO_COOLDOWN + ZEBRA_LOCK",            True,  99, False),
    ("C3: RAW_NO_COOLDOWN + SOFT_ZEBRA_LOCK (1-4)", True,  4,  False),
]

for title, ds, cfg, init_b in [
    ("REAL 27 LIVE SESSIONS | Init 3.5M", tr_real, cfg_base, 3_500_000),
    ("REAL 27 LIVE SESSIONS | Init 2.0M", tr_real, cfg_base_2m, 2_000_000),
    ("SUITE A (450k spins) | Init 3.5M", tr_A, cfg_base, 3_500_000),
    ("SUITE B (300k Aggressive) | Init 3.5M", tr_B, cfg_base, 3_500_000),
    ("SUITE A (450k spins) | Init 2.0M", tr_A, cfg_base_2m, 2_000_000),
]:
    print(f"\n=== FACTORIAL MODE TEST: {title} ===")
    print(f"{'Variant':<44} | {'Mean/hr':>9} | {'Med/hr':>9} | {'Win%':>6} | {'Bust%':>5} | {'Med/Bust':>8} | {'P95 DD':>9} | {'Max DD':>9}")
    print("-" * 116)
    for label, ncd, zlock, fast_ex in factorial_variants:
        r = sim_policy(ds, cfg, init_b, use_no_cd=ncd, zebra_lock_max_step=zlock, fast_step1_exit=fast_ex)
        print(f"{label:<44} | {r['mean_hr']:>+9,.0f} | {r['med_hr']:>+9,.0f} | {r['win_pct']:>5.1f}% | {r['bust_pct']:>4.1f}% | {r['eff']:>8,.0f} | {r['p95_dd']:>9,d} | {r['max_dd']:>9,d}")

# PART 2: Exact Comparison of Progression Geometries & Base Bets per Mode in Suite A (450k spins) & Suite B (300k)!
print("\n=== PART 2: STAKING MATRIX OPTIMIZATION ON SUITE A (450k spins) & REAL 27 (Init 3.5M, Using C2/A2 Comparison) ===")
staking_grid = [
    ("1. Base-Min 10-st All (1000/N10 GEOM)",        {'ZEBRA':(1000,10,'GEOM',2.025), 'TRANSITION':(1000,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("2. Base-Max 10-st All (1700/N10 FLAT_TBB)",    {'ZEBRA':(1700,10,'FLAT_TBB',2.025), 'TRANSITION':(1700,10,'FLAT_TBB',2.025), 'DANGER':(1700,10,'FLAT_TBB',2.025)}),
    ("3. Shield-10 (Z2000/N10 T1200/N10 D1000/N10)", {'ZEBRA':(2000,10,'GEOM',2.025), 'TRANSITION':(1200,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("4. Apex-A (Z2500/N9 T1500/N10 D1000/N10) GEOM",{'ZEBRA':(2500,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("5. Apex-B (Z3000/N9 T1500/N10 D1000/N10) GEOM",{'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("6. Apex-C (Z3000/N9 T1500/N10 D1000) FLAT",    {'ZEBRA':(3000,9,'FLAT_TBB',2.025), 'TRANSITION':(1500,10,'FLAT_TBB',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("7. Apex-D (Z3000/N9 T1500/N10 D1000) FRONT",   {'ZEBRA':(3000,9,'FRONT_BOOST',2.025), 'TRANSITION':(1500,10,'FRONT_BOOST',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("8. Apex-E (Z3500/N9 T1500/N10 D1000/N10) FLAT",{'ZEBRA':(3500,9,'FLAT_TBB',2.025), 'TRANSITION':(1500,10,'FLAT_TBB',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("9. Turbo-A (Z3500/N9 T1800/N10 D1000/N10)",    {'ZEBRA':(3500,9,'GEOM',2.025), 'TRANSITION':(1800,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("10. Turbo-B (Z3500/N9 T2200/N9 D1200/N10)",    {'ZEBRA':(3500,9,'GEOM',2.025), 'TRANSITION':(2200,9,'GEOM',2.025), 'DANGER':(1200,10,'GEOM',2.025)}),
    ("11. Turbo-C (Z4500/N8 T2000/N9 D1000/N10)",    {'ZEBRA':(4500,8,'GEOM',2.025), 'TRANSITION':(2000,9,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}),
    ("12. Pure 9-Step All (Z3000 T2000 D1000, X~2.07)",{'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(2000,9,'GEOM',2.025), 'DANGER':(1000,9,'GEOM',2.025)}),
]

print(f"{'Staking Config (RAW_NO_CD)':<46} | {'Real27 Mean/hr':>14} | {'Real MaxDD':>10} | {'A Med/hr':>9} | {'A Win%':>6} | {'A Bust%':>7} | {'Med/Bust':>8} | {'B Bust%'}")
print("-" * 124)
for label, cfg in staking_grid:
    rr = sim_policy(tr_real, cfg, 3_500_000, use_no_cd=True, zebra_lock_max_step=0)
    ra = sim_policy(tr_A, cfg, 3_500_000, use_no_cd=True, zebra_lock_max_step=0)
    rb = sim_policy(tr_B, cfg, 3_500_000, use_no_cd=True, zebra_lock_max_step=0)
    print(f"{label:<46} | {rr['mean_hr']:>+14,.0f} | {rr['max_dd']:>10,d} | {ra['med_hr']:>+9,.0f} | {ra['win_pct']:>5.1f}% | {ra['bust_pct']:>6.2f}% | {ra['eff']:>8,.0f} | {rb['bust_pct']:>6.2f}%")
