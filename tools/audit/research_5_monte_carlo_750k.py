import os, sys, math, random, time
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round
from research_1_reverse_engineering import load_clean_corpus
from research_3_staking_math import clean_calc_bet

real_sessions = load_clean_corpus()

def gen_empirical_iid_sessions(n_sess=3000, spins_per_sess=150, seed=2026):
    rng = random.Random(seed)
    return [['ZERO' if (u := rng.random()) < 0.0485 else ('RED' if u < 0.5242 else 'BLACK') for _ in range(spins_per_sess)] for _ in range(n_sess)]

def gen_adversarial_regime_sessions(n_sess=2000, spins_per_sess=150, seed=7777):
    rng = random.Random(seed)
    out = []
    for _ in range(n_sess):
        arr = []
        regime = 'NORMAL'
        ttl = rng.randint(12, 25)
        last_nz = 'RED' if rng.random() < 0.5 else 'BLACK'
        for _ in range(spins_per_sess):
            ttl -= 1
            if ttl <= 0:
                u = rng.random()
                if u < 0.30: regime, ttl = 'CALM', rng.randint(15, 30)
                elif u < 0.75: regime, ttl = 'NORMAL', rng.randint(15, 30)
                else: regime, ttl = 'STREAK_WAVE', rng.randint(10, 18)
            z_prob = 0.035 if regime == 'CALM' else (0.045 if regime == 'NORMAL' else 0.065)
            if rng.random() < z_prob:
                arr.append('ZERO')
            else:
                same_p = 0.44 if regime == 'CALM' else (0.50 if regime == 'NORMAL' else 0.62)
                c = last_nz if rng.random() < same_p else ('BLACK' if last_nz == 'RED' else 'RED')
                arr.append(c)
                last_nz = c
        out.append(arr)
    return out

def precompute_traces(outcome_lists):
    """Precomputes exact PrngDetector recommendation, raw mode, and hysteresis mode for every spin ONCE."""
    traces = []
    for outcomes in outcome_lists:
        history = []
        curr_mode = 'ZEBRA'
        prev_mode = 'ZEBRA'
        s_danger = 999
        s_curr = 0
        seq = []
        for out in outcomes:
            rec, _, _ = PrngDetectorMirror.get_recommendation_and_confidence(history)
            is_win = (out == rec and out != 'ZERO')
            m_before_hyst = curr_mode
            raw_before = PrngDetectorMirror.detect_mode(history) if history else 'ZEBRA'
            if history[-10:].count('ZERO') >= 3 and raw_before == 'ZEBRA':
                raw_before = 'TRANSITION'

            history.append(out)
            curr_mode, prev_mode, s_danger, s_curr = PrngDetectorMirror.detect_mode_with_hysteresis(
                history, prev_mode, curr_mode, s_danger, s_curr
            )
            seq.append((is_win, m_before_hyst, raw_before))
        traces.append(seq)
    return traces

t0 = time.time()
print("Generating & precomputing 27 Real + 3,000 Suite A + 2,000 Suite B (752,374 spins)...")
trace_real = precompute_traces([s['outcomes'] for s in real_sessions])
trace_A = precompute_traces(gen_empirical_iid_sessions(3000, 150, 2026))
trace_B = precompute_traces(gen_adversarial_regime_sessions(2000, 150, 7777))
print(f"Precompute done in {time.time() - t0:.2f}s.")

def run_fast(traces, cfg, init_bank=3_000_000, policy='CURRENT', reset_on_bust_step=None):
    n_sess = len(traces)
    wins = 0
    big_losses = 0
    bankrupts = 0
    total_net = 0
    total_spins = 0
    dds = []
    hr_rates = []

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

            active_raw = raw_mode if 'NO_CD' in policy else hyst_mode
            if step == 1:
                seq_start_mode = active_raw
                prev_bet = None

            if reset_on_bust_step and step > reset_on_bust_step:
                cdt = 0
                step = 1
                prev_bet = None
                seq_start_mode = active_raw

            if policy in ('LOCK_ZEBRA', 'LOCK_ZEBRA_NO_CD'):
                bet_mode = 'ZEBRA' if seq_start_mode == 'ZEBRA' else active_raw
            elif policy == 'LOCK_ZEBRA_4':
                bet_mode = 'ZEBRA' if (seq_start_mode == 'ZEBRA' and step <= 4) else active_raw
            else:
                bet_mode = active_raw

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
        if busted: bankrupts += 1
        dds.append(sess_dd)
        hr_rates.append(sess_net / len(seq) * 270.0)

    dds.sort()
    hr_rates.sort()
    return {
        'mean_hr': total_net / max(1, total_spins) * 270.0,
        'med_hr': hr_rates[len(hr_rates)//2],
        'win_pct': wins / n_sess * 100.0,
        'big_loss_pct': big_losses / n_sess * 100.0,
        'bust_pct': bankrupts / n_sess * 100.0,
        'p95_dd': dds[int(0.95 * len(dds))],
        'max_dd': dds[-1],
        'total_net': total_net,
    }

candidates = [
    ("1. Uniform Low B0=1000 / N10 / GEOM",                 {'ZEBRA':(1000,10,'GEOM',2.025), 'TRANSITION':(1000,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'CURRENT', None),
    ("2. Uniform Max B0=1700 / N10 / FLAT_TBB",             {'ZEBRA':(1700,10,'FLAT_TBB',2.025), 'TRANSITION':(1700,10,'FLAT_TBB',2.025), 'DANGER':(1700,10,'FLAT_TBB',2.025)}, 'CURRENT', None),
    ("3. v12.4 Current (Z3000/N9 T1500/N10 D1000/N10)",     {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'CURRENT', None),
    ("4. v12.4 + ZEBRA LOCK",                               {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'LOCK_ZEBRA', None),
    ("5. v12.4 + NO_COOLDOWN",                              {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'NO_COOLDOWN', None),
    ("6. v12.4 + ZEBRA LOCK + NO_COOLDOWN",                 {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'LOCK_ZEBRA_NO_CD', None),
    ("7. Flat-TBB Hybrid (Z3000/N9 T1500/N10 FLAT D1000)",  {'ZEBRA':(3000,9,'FLAT_TBB',2.025), 'TRANSITION':(1500,10,'FLAT_TBB',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'NO_COOLDOWN', None),
    ("8. Z3500/N9 T1500/N10 D1000/N10 FLAT+NO_CD",          {'ZEBRA':(3500,9,'FLAT_TBB',2.025), 'TRANSITION':(1500,10,'FLAT_TBB',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'NO_COOLDOWN', None),
    ("9. Safe Mode 10-st All (Z1700/T1300/D1000) NO_CD",    {'ZEBRA':(1700,10,'GEOM',2.025), 'TRANSITION':(1300,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'NO_COOLDOWN', None),
    ("10. Hard Stop Reset N10 (Z3000/N9 T1500/N10 D1000)",  {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'CURRENT', 10),
    ("11. Hard Stop Reset N10 + NO_CD",                     {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'NO_COOLDOWN', 10),
    ("12. Turbo 9-st All (Z3500/T2000/N9 D1200/N10) NO_CD", {'ZEBRA':(3500,9,'GEOM',2.025), 'TRANSITION':(2000,9,'GEOM',2.025), 'DANGER':(1200,10,'GEOM',2.025)}, 'NO_COOLDOWN', None),
    ("13. Ultra-Shield (Z2000/N10 T1200/N10 D1000/N10)",    {'ZEBRA':(2000,10,'GEOM',2.025), 'TRANSITION':(1200,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'CURRENT', None),
    ("14. High-Z 8-st (Z4000/N8 T1500/N10 D1000/N10)",      {'ZEBRA':(4000,8,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}, 'NO_COOLDOWN', None),
]

for suite_name, tr, init_b in [
    ("REAL 27 LIVE SESSIONS (Init 3.5M)", trace_real, 3_500_000),
    ("SUITE A: 3,000 Empirical RNG Sessions (450,000 spins, Init 3.5M)", trace_A, 3_500_000),
    ("SUITE B: 2,000 Aggressive Streak-Wave Sessions (300,000 spins, Init 3.5M)", trace_B, 3_500_000),
    ("SUITE A: 3,000 Empirical RNG Sessions (450,000 spins, Init 2.0M)", trace_A, 2_000_000),
]:
    print(f"\n====================================================================================================================")
    print(f"BENCHMARK: {suite_name}")
    print(f"====================================================================================================================")
    print(f"{'Strategy':<53} | {'Mean/hr':>9} | {'Med/hr':>9} | {'Win%':>6} | {'Loss>500k':>9} | {'Bust%':>5} | {'P95 DD':>10} | {'Max DD':>10}")
    print("-" * 127)
    for name, cfg, pol, rst in candidates:
        r = run_fast(tr, cfg, init_b, pol, rst)
        print(f"{name:<53} | {r['mean_hr']:>+9,.0f} | {r['med_hr']:>+9,.0f} | {r['win_pct']:>5.1f}% | {r['big_loss_pct']:>8.2f}% | {r['bust_pct']:>4.1f}% | {r['p95_dd']:>10,d} | {r['max_dd']:>10,d}")
