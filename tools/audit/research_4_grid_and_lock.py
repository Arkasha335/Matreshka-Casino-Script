import os, sys, math
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round
from research_1_reverse_engineering import load_clean_corpus
from research_3_staking_math import clean_calc_bet

sessions = load_clean_corpus()

def sim_custom(
    cfg,                # dict: mode -> (b0, N, shape, x_min)
    init_bank=3_000_000,
    mode_policy='CURRENT',
    stop_loss_step=None,  # e.g. None, 9, 10
):
    total_net = 0
    won = 0
    busted = 0
    worst_dd = 0
    max_st = 0
    limit_hits = 0
    dead_hits = 0
    total_spins = 0
    sess_nets = []
    sess_hrs = []

    for s in sessions:
        bank = init_bank
        peak = bank
        sess_dd = 0
        history = []
        step = 1
        cdt = 0
        curr_mode = 'ZEBRA'
        prev_mode = 'ZEBRA'
        s_danger = 999
        s_curr = 0
        seq_start_mode = 'ZEBRA'
        prev_bet = None
        sess_busted = False

        for outcome in s['outcomes']:
            if bank < 1000:
                sess_busted = True
                break
            if step == 1:
                seq_start_mode = curr_mode
                prev_bet = None

            if stop_loss_step and step > stop_loss_step:
                cdt = 0
                step = 1
                prev_bet = None
                seq_start_mode = curr_mode

            if mode_policy == 'CURRENT':
                bet_mode = curr_mode
            elif mode_policy == 'LOCK_ZEBRA':
                bet_mode = 'ZEBRA' if seq_start_mode == 'ZEBRA' else curr_mode
            elif mode_policy == 'LOCK_ZEBRA_STEP4':
                bet_mode = 'ZEBRA' if (seq_start_mode == 'ZEBRA' and step <= 4) else curr_mode
            elif mode_policy == 'LOCK_ZEBRA_CDT_GUARD':
                # Lock ZEBRA ONLY while CDT doesn't endanger step 10 (e.g. step<=5 AND mode isn't full DANGER streak >=5)
                bet_mode = 'ZEBRA' if (seq_start_mode == 'ZEBRA' and step <= 5) else curr_mode
            elif mode_policy == 'KEEP_PROFIT_TARGET':
                # Switch steps/safety curve down to curr_mode on DANGER, BUT keep target profit = seq_start_mode's B0 if CDT allows!
                bet_mode = curr_mode
            elif mode_policy == 'FAST_RECOVER_NO_CD':
                bet_mode = curr_mode
            elif mode_policy == 'LOCK_ZEBRA_FAST_EXIT':
                bet_mode = 'ZEBRA' if seq_start_mode == 'ZEBRA' else curr_mode
            else:
                bet_mode = curr_mode

            b0, t_steps, shape, xmin = cfg[bet_mode]
            # Special policy KEEP_PROFIT_TARGET: target base profit stays max(curr b0, seq_start b0) in minTbb if remaining >= 3!
            if mode_policy == 'KEEP_PROFIT_TARGET' and curr_mode != 'DANGER':
                start_b0 = cfg[seq_start_mode][0]
                b0 = max(b0, start_b0) if step <= 4 else b0

            bet = clean_calc_bet(cdt, step, b0, t_steps, bank, prev_bet, geom_x_min=xmin, shape=shape)
            if bet >= 1_000_000: limit_hits += 1
            if js_round(bet * 0.98) < cdt: dead_hits += 1

            rec, _, _ = PrngDetectorMirror.get_recommendation_and_confidence(history)
            is_win = (outcome == rec and outcome != 'ZERO')
            max_st = max(max_st, step)
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

            history.append(outcome)
            if mode_policy in ('FAST_RECOVER_NO_CD', 'LOCK_ZEBRA_FAST_EXIT'):
                # Drop 5-spin post-DANGER cooldown: if win happened (step==1) and raw=='ZEBRA', unlock immediately!
                raw = PrngDetectorMirror.detect_mode(history)
                z10 = history[-10:].count('ZERO')
                if z10 >= 3 and raw == 'ZEBRA': raw = 'TRANSITION'
                if curr_mode == 'DANGER' and s_curr < 3 and raw != 'DANGER' and step > 1:
                    curr_mode = 'DANGER'
                else:
                    if raw != curr_mode: s_curr = 1
                    else: s_curr += 1
                    curr_mode = raw
            else:
                curr_mode, prev_mode, s_danger, s_curr = PrngDetectorMirror.detect_mode_with_hysteresis(
                    history, prev_mode, curr_mode, s_danger, s_curr
                )

        if sess_busted: busted += 1
        sess_net = bank - init_bank
        total_net += sess_net
        if sess_net > 0: won += 1
        worst_dd = max(worst_dd, sess_dd)
        sess_nets.append(sess_net)
        sess_hrs.append(sess_net / len(s['outcomes']) * 270.0)

    med_hr = sorted(sess_hrs)[len(sess_hrs)//2]
    return {
        'net': total_net, 'hr': total_net / total_spins * 270.0, 'med_hr': med_hr,
        'won': won, 'n': len(sessions), 'busted': busted, 'dd': worst_dd,
        'max_st': max_st, 'lim': limit_hits, 'dead': dead_hits
    }

# 1. Trace why LOCK_ZEBRA lost on 2026-04-01 at 2M bankroll
print("=== 1. MODE POLICY TEST WITH CLEAN FIXED SIMULATOR (3 BANKROLL TIERS) ===")
for init_b in [1_000_000, 2_000_000, 3_500_000]:
    if init_b >= 3_000_000:
        cfg = {'ZEBRA': (3000, 9, 'GEOM', 2.025), 'TRANSITION': (1500, 10, 'GEOM', 2.025), 'DANGER': (1000, 10, 'GEOM', 2.025)}
    elif init_b >= 1_800_000:
        cfg = {'ZEBRA': (2000, 9, 'GEOM', 2.025), 'TRANSITION': (1200, 10, 'GEOM', 2.025), 'DANGER': (1000, 10, 'GEOM', 2.025)}
    else:
        cfg = {'ZEBRA': (1000, 9, 'GEOM', 2.025), 'TRANSITION': (1000, 10, 'GEOM', 2.025), 'DANGER': (1000, 10, 'GEOM', 2.025)}

    print(f"\n--- Init Bankroll = {init_b:,} RUB ---")
    print(f"{'Mode Policy':<22} | {'Total Net':>11} | {'Mean/hr':>9} | {'Med/hr':>9} | {'Won':>5} | {'Worst DD':>10} | {'St':>2} | {'Lim':>3} | {'Dead'}")
    print("-" * 102)
    for pol in ['CURRENT', 'LOCK_ZEBRA', 'LOCK_ZEBRA_STEP4', 'LOCK_ZEBRA_CDT_GUARD', 'KEEP_PROFIT_TARGET', 'FAST_RECOVER_NO_CD', 'LOCK_ZEBRA_FAST_EXIT']:
        r = sim_custom(cfg, init_b, pol)
        print(f"{pol:<22} | {r['net']:>+11,d} | {r['hr']:>+9,.0f} | {r['med_hr']:>+9,.0f} | {r['won']:>2}/{r['n']:<2} | {r['dd']:>10,d} | {r['max_st']:>2} | {r['lim']:>3} | {r['dead']}")

# 2. Grid Search over ZEBRA (b0, N, shape), TRANSITION (b0, N, shape), DANGER (b0, N, shape) at Init = 3.5M and Init = 2.0M!
print("\n=== 2. SINGLE-MODE GRID SEARCH (ISOLATING EACH PARAMETER AT BANKROLL = 3.5M & 2.0M) ===")
print("A. Varying ONLY ZEBRA (keeping TRANSITION=1500/N10, DANGER=1000/N10) at Init=3,500,000:")
print(f"{'ZEBRA Config':<28} | {'Total Net':>11} | {'Mean/hr':>9} | {'Med/hr':>9} | {'Won':>5} | {'Worst DD':>10} | {'St':>2} | {'Lim':>3} | {'Dead'}")
print("-" * 105)
for N_z in [8, 9, 10]:
    b0_list = [1000, 1500, 2000, 3000, 4000, 5000, 6500] if N_z == 8 else ([1000, 2000, 3000, 3500] if N_z == 9 else [1000, 1500, 2000, 3000])
    for b0_z in b0_list:
        for sh in ['GEOM', 'FLAT_TBB']:
            if sh == 'FLAT_TBB' and b0_z == 1000: continue
            cfg = {'ZEBRA': (b0_z, N_z, sh, 2.025), 'TRANSITION': (1500, 10, 'GEOM', 2.025), 'DANGER': (1000, 10, 'GEOM', 2.025)}
            r = sim_custom(cfg, 3_500_000, 'CURRENT')
            print(f"Z: B0={b0_z:4d}, N={N_z:2d}, {sh:<8} | {r['net']:>+11,d} | {r['hr']:>+9,.0f} | {r['med_hr']:>+9,.0f} | {r['won']:>2}/{r['n']:<2} | {r['dd']:>10,d} | {r['max_st']:>2} | {r['lim']:>3} | {r['dead']}")

print("\nB. Varying ONLY TRANSITION & DANGER (keeping ZEBRA=3000/N9/GEOM) at Init=3,500,000:")
print(f"{'TRANS/DANGER Config':<34} | {'Total Net':>11} | {'Mean/hr':>9} | {'Med/hr':>9} | {'Won':>5} | {'Worst DD':>10} | {'St':>2} | {'Lim':>3} | {'Dead'}")
print("-" * 110)
for t_b0, t_n in [(1000,10), (1500,10), (1700,10), (2000,9), (2500,9)]:
    for d_b0, d_n in [(1000,10), (1000,11), (1500,10)]:
        cfg = {'ZEBRA': (3000, 9, 'GEOM', 2.025), 'TRANSITION': (t_b0, t_n, 'GEOM', 2.025), 'DANGER': (d_b0, d_n, 'GEOM', 2.025)}
        r = sim_custom(cfg, 3_500_000, 'CURRENT')
        print(f"T={t_b0}/N{t_n} D={d_b0}/N{d_n:<11} | {r['net']:>+11,d} | {r['hr']:>+9,.0f} | {r['med_hr']:>+9,.0f} | {r['won']:>2}/{r['n']:<2} | {r['dd']:>10,d} | {r['max_st']:>2} | {r['lim']:>3} | {r['dead']}")
