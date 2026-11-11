import os, sys, math
sys.path.append(os.path.dirname(__file__))
from verify_final_v12_5_release import load_clean, gen_empirical, precompute_full, solve_exact_budget_x

TABLE_LIMIT = 1_000_000

def floor_win(bet):
    return (bet * 98) // 100

def geom_sum_factor(n, x=2.025):
    return (math.pow(x, n) - 1.0) / (x - 1.0)

def exact_bet_1m_floor(cdt, step, base_bet, target_steps, bankroll, prev_bet):
    if bankroll < 1000:
        return max(0, int(bankroll))
    base_bet = max(1000, min(base_bet, bankroll, TABLE_LIMIT))
    if cdt <= 0 or step <= 1:
        return int(round(base_bet))

    rem = max(1, target_steps - step + 1)

    # Strict game floor payout: ensure floor(bet * 98 / 100) >= cdt + base_bet
    min_tbb = math.ceil(((cdt + base_bet) * 100) / 98.0)
    while floor_win(min_tbb) < cdt + base_bet:
        min_tbb += 1

    pb = prev_bet if (prev_bet is not None and prev_bet > 0) else base_bet

    if rem == 1:
        cap = min(TABLE_LIMIT, bankroll)
        bet = min(min_tbb, cap) if cdt < cap * 0.30 else cap
        return max(1000, min(cap, int(round(bet))))

    opt_x, _ = solve_exact_budget_x(pb, rem, bankroll, TABLE_LIMIT, min_x=2.025, max_x=3.20)
    geom_bet = int(math.floor(pb * opt_x + 0.5))
    bet = max(min_tbb, geom_bet)

    # Generalized Horizon Guard on rem == 2 with strict floor payout check
    if rem == 2:
        max_pen_table = (TABLE_LIMIT * 98) // 100 - cdt - 100
        max_pen_wallet = math.floor((0.98 * bankroll - cdt - 100) / 1.98)
        max_safe = min(max_pen_table, max_pen_wallet)
        min_be = math.ceil(((cdt + 100) * 100) / 98.0)
        while floor_win(min_be) < cdt + 100:
            min_be += 1
        if max_safe >= min_be:
            bet = min(bet, max_safe)

    return max(1000, min(int(round(bet)), TABLE_LIMIT, bankroll))


def make_1m_cfg(z_spec, t_spec, d_spec):
    specs = {'ZEBRA': z_spec, 'TRANSITION': t_spec, 'DANGER': d_spec}
    def fn(mode, cap):
        cap = max(10_000, cap)
        # Strict 1M table ceiling, scaled smoothly only if wallet cycle capacity < 1M ceiling (cap < 1.92M)
        effective_ceiling = min(TABLE_LIMIT, cap / 1.92)
        scale = max(0.15, effective_ceiling / 1_000_000.0)
        b0, n = specs[mode]
        while n > 5 and 1000 * geom_sum_factor(n) > cap:
            n -= 1
        max_b0_budget = max(1000, int(math.floor(cap / geom_sum_factor(n) / 100.0) * 100))
        scaled_b0 = max(1000, min(TABLE_LIMIT, max_b0_budget, int(math.floor(b0 * scale / 100.0 + 0.5) * 100)))
        return scaled_b0, n
    return fn


def make_adaptive_apex(low_specs, mid_specs, high_specs):
    """
    Tests tiered APEX calibrated to bankroll resilience at fixed 1M table limit:
    - low (< 2.5M): prioritize survivability & steady profit without busting easily
    - mid (2.5M .. 4.5M): strong EV + survival
    - high (>= 4.5M): exploit deep cushion for ~700k-900k+/hr with ~96% real winrate
    """
    def fn(mode, cap):
        if cap >= 4_500_000:
            return make_1m_cfg(*high_specs)(mode, cap)
        elif cap >= 2_500_000:
            return make_1m_cfg(*mid_specs)(mode, cap)
        else:
            return make_1m_cfg(*low_specs)(mode, cap)
    return fn


def run_bench_1m(traces, cfg_fn, init_bank, no_cd=True, zl_thresh=3_000_000, lock_seq_n=False):
    wins = busts = neg_wins = inv_err = 0
    hrs, dds = [], []
    for seq in traces:
        bank = init_bank; peak = bank; sess_dd = 0
        step = 1; cdt = 0; prev_bet = None; seq_start = 'ZEBRA'; seq_n = None; busted = False
        for is_win, hyst_m, raw_m in seq:
            if bank < 1000:
                busted = True
                break
            active_m = raw_m if no_cd else hyst_m
            if step == 1:
                seq_start = active_m
                prev_bet = None
                seq_n = cfg_fn(active_m, bank)[1]
            cycle_cap = bank + cdt
            use_zl = (zl_thresh is not None) and (cycle_cap >= zl_thresh) and (seq_start == 'ZEBRA')
            bm = 'ZEBRA' if use_zl else active_m
            b0, n_mode = cfg_fn(bm, cycle_cap)
            eff_n = seq_n if lock_seq_n else (min(seq_n, n_mode) if seq_n is not None else n_mode)

            bet = exact_bet_1m_floor(cdt, step, b0, eff_n, bank, prev_bet)
            if bet < 1000 or bet > TABLE_LIMIT or bet > bank:
                inv_err += 1

            if is_win:
                net = floor_win(bet)
                if bet < min(TABLE_LIMIT, bank) and cdt > 0 and (net - cdt) < 0:
                    neg_wins += 1
                bank += net
                cdt = max(0, cdt - net)
                if cdt == 0:
                    step = 1
            else:
                bank -= bet
                cdt += bet
                step += 1
            prev_bet = bet
            if bank > peak: peak = bank
            sess_dd = max(sess_dd, peak - bank)
        net_s = bank - init_bank
        if net_s > 0: wins += 1
        if busted: busts += 1
        dds.append(sess_dd)
        hrs.append(net_s / len(seq) * 270.0)
    hrs.sort(); dds.sort()
    n = len(traces)
    return {
        'win': wins/n*100, 'bust': busts/n*100,
        'med': hrs[n//2], 'p75': hrs[int(0.75*n)], 'p90': hrs[int(0.90*n)],
        'max_dd': dds[-1], 'errs': inv_err + neg_wins
    }

if __name__ == '__main__':
    tr_real = precompute_full([x[1] for x in load_clean()])
    tr_mc100 = precompute_full(gen_empirical(2000, 100, 2026))
    tr_mc270 = precompute_full(gen_empirical(2000, 270, 7777))

    candidates = [
        ("SHIELD      (1.7/1.2/1.0, N10/10/10)",        make_1m_cfg((1700,10),(1200,10),(1000,10)), False, None),
        ("APEX_9/10   (3.5/2.0/1.2, N9/10/10)",         make_1m_cfg((3500,9), (2000,10),(1200,10)), True,  3_000_000),
        ("APEX_9/9    (3.5/2.5/1.5, N9/9/9)",           make_1m_cfg((3500,9), (2500,9), (1500,9)),  True,  3_000_000),
        ("APEX_8/9/10 (4.5/2.5/1.5, N8/9/10)",          make_1m_cfg((4500,8), (2500,9), (1500,10)), True,  3_000_000),
        ("APEX_8/10   (5.0/2.5/1.4, N8/10/10)",         make_1m_cfg((5000,8), (2500,10),(1400,10)), True,  3_000_000),
        ("APEX_8/9/9  (4.5/3.0/1.5, N8/9/9)",           make_1m_cfg((4500,8), (3000,9), (1500,9)),  True,  3_000_000),
        ("APEX_TIERS  (2.0M:9/10|2.5M:8/10|4.5M:8/9/9)",make_adaptive_apex(((3500,9),(2000,10),(1200,10)), ((4500,8),(2500,10),(1400,10)), ((4800,8),(3000,9),(1600,9))), True, 2_500_000),
        ("TURBO_8/8/9 (6.0/4.0/1.7, N8/8/9)",           make_1m_cfg((6000,8), (4000,8), (1700,9)),  True,  3_000_000),
        ("TURBO_8/8/8 (6.5/4.5/2.5, N8/8/8)",           make_1m_cfg((6500,8), (4500,8), (2500,8)),  True,  3_000_000),
        ("TURBO_7/8/8 (9.0/5.5/3.0, N7/8/8)",           make_1m_cfg((9000,7), (5500,8), (3000,8)),  True,  3_000_000),
    ]

    for b_init in [1_000_000, 2_000_000, 3_800_000, 6_500_000]:
        print(f"\n=== STRICT M = 1,000,000 RUB | BANKROLL = {b_init:,} | GAME FLOOR PAYOUT ===")
        print(f"{'Candidate':<46} | {'R27 W%':>6} {'R27 Med/h':>10} {'R27 P90/h':>10} | {'MC100 W%':>8} {'MC100 Med':>10} | {'1h W%':>6} {'1h Med/h':>10} {'1h P90/h':>10} {'Bust%':>6} | Err")
        print("-" * 160)
        for lbl, fn, ncd, zlt in candidates:
            rr = run_bench_1m(tr_real, fn, b_init, ncd, zlt)
            m1 = run_bench_1m(tr_mc100, fn, b_init, ncd, zlt)
            m2 = run_bench_1m(tr_mc270, fn, b_init, ncd, zlt)
            errs = rr['errs'] + m1['errs'] + m2['errs']
            print(f"{lbl:<46} | {rr['win']:>5.1f}% {rr['med']:>+10,.0f} {rr['p90']:>+10,.0f} | {m1['win']:>7.1f}% {m1['med']:>+10,.0f} | {m2['win']:>5.1f}% {m2['med']:>+10,.0f} {m2['p90']:>+10,.0f} {m2['bust']:>5.1f}% | {errs}")
