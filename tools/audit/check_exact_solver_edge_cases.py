import math

def js_round(x): return math.floor(x + 0.5)

def solve_exact_budget_x(prev_b, rem_steps, rem_wallet, table_limit, min_x=2.025, max_x=2.65):
    x_table = math.pow(table_limit / max(1, prev_b), 1.0 / rem_steps)
    hi = min(max_x, x_table)
    if hi < min_x:
        return min_x, min(table_limit, rem_wallet)
    def geom_sum(x):
        s = 0.0; b = float(prev_b)
        for _ in range(rem_steps):
            b *= x; s += b
        return s
    if geom_sum(hi) <= rem_wallet:
        return hi, min(table_limit, round(prev_b * (hi ** rem_steps)))
    lo = 1.01
    if geom_sum(min_x) > rem_wallet:
        for _ in range(25):
            mid = 0.5 * (lo + min_x)
            if geom_sum(mid) <= rem_wallet: lo = mid
            else: min_x = mid
        return lo, min(table_limit, round(prev_b * (lo ** rem_steps)))
    lo = min_x
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        if geom_sum(mid) <= rem_wallet: lo = mid
        else: hi = mid
    return lo, min(table_limit, round(prev_b * (lo ** rem_steps)))

def exact_solver_bet(cdt, step, base_bet, target_steps, bankroll, table_limit, prev_bet, use_horizon_guard=True):
    base_bet = max(1000, min(base_bet, bankroll, table_limit))
    if cdt <= 0 or step <= 1:
        return js_round(base_bet)
    rem = max(1, target_steps - step + 1)
    min_tbb = math.ceil((cdt + base_bet) / 0.98)
    pb = prev_bet if (prev_bet is not None and prev_bet > 0) else base_bet
    if rem == 1:
        cap = min(table_limit, bankroll)
        if cdt < cap * 0.30:
            bet = min(min_tbb, cap)
        else:
            bet = cap
        return max(1000, js_round(bet))
    opt_x, term_proj = solve_exact_budget_x(pb, rem, bankroll, table_limit, min_x=2.025, max_x=2.65)
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

def inspect_ladder(title, b0, N, W, M, switch=None):
    print(f"\n=== {title} | W={W:,} | M={M:,} | N={N} ===")
    cdt = 0; rem_w = W; pb = None; seq_n = N; cur_b0 = b0; cur_m = 'BASE'
    for s in range(1, N + 1):
        if switch and s in switch:
            cur_m, cur_b0, mode_n = switch[s]
            seq_n = min(seq_n, mode_n)
        bet = exact_solver_bet(cdt, s, cur_b0, seq_n, rem_w, M, pb)
        net_win = js_round(bet * 0.98) - cdt
        mult = bet / pb if pb else 1.0
        print(f"  St {s:2d}/{seq_n} ({cur_m:<5}) | Bet={bet:>10,d} ({mult:.3f}x) | CDT={cdt:>10,d} | RemW After={rem_w-bet:>10,d} | NetOnWin={net_win:>+9,d}")
        if net_win <= 0:
            print(f"  !! WARNING: NEGATIVE NET ON WIN AT STEP {s}: {net_win}")
        cdt += bet; rem_w -= bet; pb = bet

inspect_ladder("1. Low Bankroll W=1.5M, M=1M, N=9, B0=1000", 1000, 9, 1_500_000, 1_000_000)
inspect_ladder("2. Mid Bankroll W=2.0M, M=1M, N=10, B0=1000", 1000, 10, 2_000_000, 1_000_000)
inspect_ladder("3. Mid Bankroll W=2.0M, M=2M, N=10, B0=1000", 1000, 10, 2_000_000, 2_000_000)
inspect_ladder("4. High Bankroll W=3.8M, M=2M, N=10, B0=2000", 2000, 10, 3_800_000, 2_000_000)
inspect_ladder("5. Whale W=6.5M, M=2M, N=9, B0=5500 (APEX)", 5500, 9, 6_500_000, 2_000_000)
inspect_ladder("6. Whale W=6.5M, M=2M, N=8, B0=10000 (TURBO)", 10000, 8, 6_500_000, 2_000_000)
inspect_ladder("7. Switch Z(6k/9)->T(3k/10)->D(2k/10) at W=6.5M, M=2M", 6000, 9, 6_500_000, 2_000_000,
               switch={3:('TRANS',3000,10), 5:('DANGR',2000,10)})
inspect_ladder("8. Switch T(3k/10)->D(2k/10) at W=6.5M, M=2M", 3000, 10, 6_500_000, 2_000_000,
               switch={4:('DANGR',2000,10)})
