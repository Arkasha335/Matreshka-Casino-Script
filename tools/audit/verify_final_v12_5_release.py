import os, sys, math
sys.path.append(os.path.dirname(__file__))
from engine_mirror import js_round
from research_10_high_yield_and_2m_cap import load_clean, gen_empirical, precompute_full

def solve_exact_budget_x(prev_b, rem_steps, rem_wallet, table_limit, min_x=2.025, max_x=3.20):
    x_table = math.pow(table_limit / max(1, prev_b), 1.0 / rem_steps)
    hi = min(max_x, x_table)

    def geom_sum(x):
        s = 0.0
        b = float(prev_b)
        for _ in range(rem_steps):
            b *= x
            s += b
        return s

    if hi < min_x:
        # Even min_x exceeds table_limit on rem_steps (e.g. near cap late in cycle).
        # Prefer min_x if wallet covers it; otherwise solve down to fit rem_wallet.
        if geom_sum(min_x) <= rem_wallet:
            return min_x, min(table_limit, rem_wallet)
        lo = 1.01
        hi_fallback = min_x
        if geom_sum(lo) > rem_wallet:
            return lo, min(table_limit, rem_wallet)
        for _ in range(25):
            mid = 0.5 * (lo + hi_fallback)
            if geom_sum(mid) <= rem_wallet:
                lo = mid
            else:
                hi_fallback = mid
        return lo, min(table_limit, round(prev_b * (lo ** rem_steps)))

    if geom_sum(hi) <= rem_wallet:
        return hi, min(table_limit, round(prev_b * (hi ** rem_steps)))

    lo = 1.01
    if geom_sum(min_x) > rem_wallet:
        if geom_sum(lo) > rem_wallet:
            return lo, min(table_limit, rem_wallet)
        hi_w = min_x
        for _ in range(25):
            mid = 0.5 * (lo + hi_w)
            if geom_sum(mid) <= rem_wallet:
                lo = mid
            else:
                hi_w = mid
        return lo, min(table_limit, round(prev_b * (lo ** rem_steps)))

    lo = min_x
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        if geom_sum(mid) <= rem_wallet:
            lo = mid
        else:
            hi = mid
    return lo, min(table_limit, round(prev_b * (lo ** rem_steps)))


def exact_solver_bet(cdt, step, base_bet, target_steps, bankroll, table_limit, prev_bet, use_horizon_guard=True):
    if bankroll < 1000:
        return max(0, int(bankroll))
    base_bet = max(1000, min(base_bet, bankroll, table_limit))
    if cdt <= 0 or step <= 1:
        return js_round(base_bet)

    rem = max(1, target_steps - step + 1)
    min_tbb = math.ceil((cdt + base_bet) / 0.98)
    pb = prev_bet if (prev_bet is not None and prev_bet > 0) else base_bet

    if rem == 1:
        cap = min(table_limit, bankroll)
        # Small partial debt cleanup (< 30% of cap): recover debt cleanly instead of over-betting 1M-2M over tiny residue
        if cdt < cap * 0.30:
            bet = min(min_tbb, cap)
        else:
            bet = cap
        return max(1000, min(cap, js_round(bet)))

    opt_x, _ = solve_exact_budget_x(pb, rem, bankroll, table_limit, min_x=2.025, max_x=3.20)
    geom_bet = js_round(pb * opt_x)
    bet = max(min_tbb, geom_bet)

    if use_horizon_guard and rem == 2:
        max_pen_table = math.floor(table_limit * 0.98) - cdt - 100
        max_pen_wallet = math.floor((0.98 * bankroll - cdt - 100) / 1.98)
        max_safe = min(max_pen_table, max_pen_wallet)
        min_breakeven = math.ceil((cdt + 100) / 0.98)
        if max_safe >= min_breakeven:
            bet = min(bet, max_safe)

    return js_round(max(1000, min(bet, table_limit, bankroll)))


def make_universal_preset(z_spec, t_spec, d_spec, min_low_cap_n=None):
    """
    Scales cleanly for ANY bankroll (500k .. 10M+) and ANY table limit (1M, 2M, custom).
    Notice scale = min(tableLimit, cycleCapital / 1.92) / 1_000_000.
    For tiny wallets (cap < 1.1M) where B0=1000 over N=10 exceeds wallet (~1.05M needed for 10 steps @ 2.025x),
    optional low-cap N clamp guarantees step N always stays geometrically viable.
    """
    specs = {'ZEBRA': z_spec, 'TRANSITION': t_spec, 'DANGER': d_spec}
    def fn(mode, cap, limit):
        effective_ceiling = min(limit, cap / 1.92)
        scale = max(0.15, effective_ceiling / 1_000_000.0)
        b0, n = specs[mode]
        if min_low_cap_n is not None and cap < 1_150_000:
            n = min(n, min_low_cap_n)
        elif cap < 700_000:
            n = min(n, 8)
        scaled_b0 = max(1000, int(round(b0 * scale / 100.0) * 100))
        # Safety check: ensure 1000 * sum_{0..n-1} 2.03^i doesn't vastly exceed cap; if scale == 0.52 (1M bank), B0=1500 @ N9 sum is ~940k!
        return scaled_b0, n
    return fn


def run_bench(traces, cfg_fn, init_bank, table_limit, no_cd=True, zl_thresh=3_000_000, lock_seq_n=False):
    wins = busts = 0
    neg_wins = invariant_err = 0
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
                seq_n = cfg_fn(active_m, bank, table_limit)[1]

            cycle_cap = bank + cdt
            use_zl = (zl_thresh is not None) and (cycle_cap >= zl_thresh) and (seq_start == 'ZEBRA')
            bm = 'ZEBRA' if use_zl else active_m
            b0, n_mode = cfg_fn(bm, cycle_cap, table_limit)
            eff_n = seq_n if lock_seq_n else (min(seq_n, n_mode) if seq_n is not None else n_mode)

            bet = exact_solver_bet(cdt, step, b0, eff_n, bank, table_limit, prev_bet)
            if bet < 1000 or bet > bank or bet > table_limit:
                invariant_err += 1
            if is_win:
                net = js_round(bet * 0.98)
                if bet < min(table_limit, bank) and cdt > 0 and (net - cdt) < 0:
                    neg_wins += 1
                bank += net
                cdt = max(0, js_round(cdt - net))
                if cdt < 10:
                    cdt = 0
                if cdt == 0:
                    step = 1
            else:
                bank -= bet
                cdt += bet
                step += 1
            prev_bet = bet
            if bank > peak:
                peak = bank
            sess_dd = max(sess_dd, peak - bank)
        net_s = bank - init_bank
        if net_s > 0:
            wins += 1
        if busted:
            busts += 1
        dds.append(sess_dd)
        hrs.append(net_s / len(seq) * 270.0)
    hrs.sort(); dds.sort()
    n = len(traces)
    mean_hr = sum(hrs) / n
    return {
        'win': wins / n * 100,
        'bust': busts / n * 100,
        'med': hrs[n // 2],
        'mean': mean_hr,
        'p75': hrs[int(0.75 * n)],
        'p90': hrs[int(0.90 * n)],
        'max_dd': dds[-1],
        'inv_err': invariant_err,
        'neg_win': neg_wins,
    }


if __name__ == '__main__':
    real_raw = load_clean()
    tr_real = precompute_full([x[1] for x in real_raw])
    tr_mc100 = precompute_full(gen_empirical(2000, 100, 2026))
    tr_mc270 = precompute_full(gen_empirical(2000, 270, 7777))

    candidates = [
        ("SHIELD (1.7k/1.2k/1.0k, N10/10/10, noCD=F, ZL=None)", make_universal_preset((1700,10),(1200,10),(1000,10), 9), False, None, True),
        ("APEX_A (3.0k/1.5k/1.0k, N9/10/10, minN)",              make_universal_preset((3000,9), (1500,10),(1000,10), 9), True, 3_000_000, False),
        ("APEX_B (3.0k/1.5k/1.0k, N9/10/10, lockSeqN)",          make_universal_preset((3000,9), (1500,10),(1000,10), 9), True, 3_000_000, True),
        ("APEX_C (3.5k/2.0k/1.2k, N9/9/10, minN)",               make_universal_preset((3500,9), (2000,9), (1200,10), 9), True, 3_000_000, False),
        ("APEX_D (4.0k/2.5k/1.5k, N9/9/9, lockSeqN)",            make_universal_preset((4000,9), (2500,9), (1500,9),  9), True, 3_000_000, True),
        ("APEX_E (4.5k/3.0k/1.5k, N8/9/9, minN)",                make_universal_preset((4500,8), (3000,9), (1500,9),  8), True, 3_000_000, False),
        ("TURBO_A (6.0k/4.0k/1.7k, N8/8/9, minN)",               make_universal_preset((6000,8), (4000,8), (1700,9),  8), True, 3_000_000, False),
        ("TURBO_B (6.0k/4.0k/1.7k, N8/8/9, lockSeqN)",           make_universal_preset((6000,8), (4000,8), (1700,9),  8), True, 3_000_000, True),
    ]

    configs = [
        (1_000_000, [1_000_000, 2_000_000, 3_800_000, 6_500_000]),
        (2_000_000, [2_000_000, 3_800_000, 6_500_000]),
    ]

    for lim, banks in configs:
        for b_init in banks:
            print(f"\n=== LIMIT M={lim:,} | BANKROLL={b_init:,} ===")
            print(f"{'Candidate':<48} | {'R27 W%':>6} {'R27 Med/h':>10} {'R27 P90/h':>10} | {'MC100 W%':>8} {'MC100 Med':>10} | {'MC270 W%':>8} {'MC270 Med':>10} {'MC270 P90':>10} {'Bust%':>6} | Errs")
            print("-" * 165)
            for lbl, fn, ncd, zlt, lsn in candidates:
                rr = run_bench(tr_real, fn, b_init, lim, ncd, zlt, lsn)
                m1 = run_bench(tr_mc100, fn, b_init, lim, ncd, zlt, lsn)
                m2 = run_bench(tr_mc270, fn, b_init, lim, ncd, zlt, lsn)
                errs = rr['inv_err'] + rr['neg_win'] + m1['inv_err'] + m1['neg_win'] + m2['inv_err'] + m2['neg_win']
                print(f"{lbl:<48} | {rr['win']:>5.1f}% {rr['med']:>+10,.0f} {rr['p90']:>+10,.0f} | {m1['win']:>7.1f}% {m1['med']:>+10,.0f} | {m2['win']:>7.1f}% {m2['med']:>+10,.0f} {m2['p90']:>+10,.0f} {m2['bust']:>5.1f}% | {errs}")
