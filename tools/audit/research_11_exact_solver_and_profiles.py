import os, sys, math, random, json, glob, hashlib
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round
from research_10_high_yield_and_2m_cap import load_clean, gen_empirical, precompute_full

def solve_exact_budget_x(prev_b, rem_steps, rem_wallet, table_limit, min_x=2.025, max_x=2.65):
    """
    Exact nonlinear solver via binary search:
    Finds the highest growth factor X in [min_x, max_x] such that:
    1) Geometric sequence B_j = prev_b * X^j (for j=1..rem_steps) never exceeds table_limit (B_{rem_steps} <= table_limit)
    2) Cumulative future spend sum_{j=1..rem_steps} B_j <= rem_wallet (exact bankroll safety!)
    Returns (opt_x, terminal_bet_projected, max_affordable_terminal)
    """
    # First check absolute max X allowed by table_limit
    x_table = math.pow(table_limit / max(1, prev_b), 1.0 / rem_steps)
    hi = min(max_x, x_table)
    if hi < min_x:
        # Even min_x exceeds table_limit on rem_steps
        return min_x, min(table_limit, rem_wallet)

    # Check if 'hi' already fits in rem_wallet
    def geom_sum(x):
        s = 0.0
        b = float(prev_b)
        for _ in range(rem_steps):
            b *= x
            s += b
        return s

    if geom_sum(hi) <= rem_wallet:
        return hi, min(table_limit, round(prev_b * (hi ** rem_steps)))

    # If even min_x exceeds rem_wallet, solve down to 1.0 or return max fitting
    lo = 1.01
    if geom_sum(min_x) > rem_wallet:
        # Not enough wallet to keep min_x growth over rem_steps -> shrink terminal bet or fewer steps
        for _ in range(25):
            mid = 0.5 * (lo + min_x)
            if geom_sum(mid) <= rem_wallet: lo = mid
            else: min_x = mid
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
    """
    Calculates exact next bet using the Exact Geometric Budget Solver:
    - Always maximizes utilization up to min(table_limit, wallet_budget_for_rem_steps).
    - Never decreases steps unless wallet itself cannot afford 1 more breakeven step.
    - Enforces 2% commission coverage & penultimate horizon guard against dead final step.
    """
    base_bet = max(1000, min(base_bet, bankroll, table_limit))
    if cdt <= 0 or step <= 1:
        return js_round(base_bet)

    rem = max(1, target_steps - step + 1)
    min_tbb = math.ceil((cdt + base_bet) / 0.98)

    # Remaining steps after this spin if this loses? Just rem!
    # Check what terminal bet fits inside CURRENT wallet across 'rem' steps
    pb = prev_bet if (prev_bet is not None and prev_bet > 0) else base_bet

    if rem == 1:
        # Final step: push ALL the way up to min(table_limit, wallet) as requested,
        # unless it's a tiny leftover partial debt (< 30% of cap) after a partial win.
        cap = min(table_limit, bankroll)
        if cdt < cap * 0.30:
            bet = min(min_tbb, cap)
        else:
            bet = cap
        return max(1000, js_round(bet))

    opt_x, term_proj = solve_exact_budget_x(pb, rem, bankroll, table_limit, min_x=2.025, max_x=2.65)
    geom_bet = js_round(pb * opt_x)
    bet = max(min_tbb, geom_bet)

    # Horizon Guard on penultimate step (rem == 2):
    # Ensure CDT + bet doesn't exceed 0.98 * terminal_ceiling, so Step N still recovers in profit!
    if use_horizon_guard and rem == 2:
        # Remaining wallet after losing step N-1 would be (bankroll - bet); Step N bet can be min(table_limit, bankroll - bet)
        # Wait: CDT + bet <= 0.98 * min(table_limit, bankroll - bet)
        # Solve: 1.98 * bet <= 0.98 * bankroll - CDT  AND  bet <= 0.98 * table_limit - CDT
        max_pen_table = math.floor(table_limit * 0.98) - cdt - 100
        max_pen_wallet = math.floor((0.98 * bankroll - cdt - 100) / 1.98)
        max_safe = min(max_pen_table, max_pen_wallet)
        min_breakeven = math.ceil((cdt + 100) / 0.98)
        if max_safe >= min_breakeven:
            bet = min(bet, max_safe)

    return js_round(max(1000, min(bet, table_limit, bankroll)))

real_raw = load_clean()
tr_real = precompute_full([x[1] for x in real_raw])
tr_mc100 = precompute_full(gen_empirical(2000, 100, 2026))

def run_solver_bench(traces, cfg_fn, init_bank, table_limit, no_cd=True, zebra_lock=True):
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
                seq_n = cfg_fn(active_m, bank, table_limit)[1]
            bm = 'ZEBRA' if (zebra_lock and seq_start == 'ZEBRA') else active_m
            b0, n_mode = cfg_fn(bm, bank + cdt, table_limit)
            eff_n = min(seq_n, n_mode) if seq_n is not None else n_mode

            bet = exact_solver_bet(cdt, step, b0, eff_n, bank, table_limit, prev_bet)
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
    return {'win': wins/n*100, 'bust': busts/n*100, 'med': hrs[n//2], 'p75': hrs[int(0.75*n)], 'p90': hrs[int(0.90*n)], 'max_dd': dds[-1]}

# Print exact step-by-step ladders for our proposed Exact Solver at BOTH 1M & 2M limits and 2M / 3.8M / 6.5M bankrolls!
print("=== EXACT GEOMETRIC SOLVER LADDERS CHECK ===")
def show_ladder(name, b0, N, W, M):
    cdt = 0; pb = None; rem_w = W
    bets = []
    for s in range(1, N + 1):
        b = exact_solver_bet(cdt, s, b0, N, rem_w, M, pb)
        bets.append((s, b, cdt, round(b*0.98) - cdt))
        cdt += b; rem_w -= b; pb = b
        if rem_w < 1000: break
    print(f"{name} (Sum={cdt:,}/{W:,}): " + " -> ".join(f"S{s}:{b:,}(+{pi:,})" for s,b,c,pi in bets))

show_ladder("W=2.0M, M=2M, N=10, B0=1000", 1000, 10, 2_000_000, 2_000_000)
show_ladder("W=3.8M, M=2M, N=10, B0=2000", 2000, 10, 3_800_000, 2_000_000)
show_ladder("W=6.5M, M=2M, N=9,  B0=5000", 5000, 9,  6_500_000, 2_000_000)
show_ladder("W=6.5M, M=2M, N=8,  B0=10000",10000,8,  6_500_000, 2_000_000)
show_ladder("W=6.5M, M=1M, N=9,  B0=3000", 3000, 9,  6_500_000, 1_000_000)
show_ladder("W=6.5M, M=1M, N=8,  B0=5000", 5000, 8,  6_500_000, 1_000_000)

# Benchmark Exact Solver Presets across ALL 3 profiles!
def make_preset(name, z_spec, t_spec, d_spec):
    def fn(mode, cap, limit):
        # Scale B0 cleanly proportionally if limit == 2M AND cap >= 3.8M vs 1M!
        scale = min(limit, max(1_000_000, cap / 1.92)) / 1_000_000.0
        b0, n = {'ZEBRA': z_spec, 'TRANSITION': t_spec, 'DANGER': d_spec}[mode]
        scaled_b0 = max(1000, int(round(b0 * scale / 100.0) * 100))
        return scaled_b0, n
    return fn

presets = [
    ("SHIELD (N10/10/10, base scale 1.7k/1.2k/1.0k)", make_preset("S", (1700,10), (1200,10), (1000,10)), False, False),
    ("APEX BALANCED (N9/10/10, 3k/1.5k/1k @ 1M)",     make_preset("A", (3000,9),  (1500,10), (1000,10)), True,  True),
    ("APEX PRO HIGH-EV (N8/9/9, 4.5k/3k/1.5k @ 1M)",  make_preset("AP",(4500,8),  (3000,9),  (1500,9)),  True,  True),
    ("TURBO ALL-IN 8-ST (N8/8/9, 6k/4k/1.7k @ 1M)",   make_preset("T", (6000,8),  (4000,8),  (1700,9)),  True,  True),
]

for lim, bank_list in [(1_000_000, [2_000_000, 3_800_000, 6_500_000]), (2_000_000, [3_800_000, 6_500_000])]:
    for b_init in bank_list:
        print(f"\n=== BENCHMARK: Limit M={lim:,} | Bank={b_init:,} ===")
        print(f"{'Preset':<47} | {'R27 Win':>7} {'R27 Med/h':>10} {'R27 P90/h':>10} {'R27 DD':>9} | {'MC100 Win':>9} {'MC Bust':>7} {'MC Med/h':>10} {'MC P75/h':>10}")
        print("-" * 133)
        for lbl, fn, ncd, zl in presets:
            use_zl = zl and (b_init >= 3_000_000)
            rr = run_solver_bench(tr_real, fn, b_init, lim, ncd, use_zl)
            rm = run_solver_bench(tr_mc100, fn, b_init, lim, ncd, use_zl)
            print(f"{lbl:<47} | {rr['win']:>6.1f}% {rr['med']:>+10,.0f} {rr['p90']:>+10,.0f} {rr['max_dd']:>9,d} | {rm['win']:>8.1f}% {rm['bust']:>6.2f}% {rm['med']:>+10,.0f} {rm['p75']:>+10,.0f}")
