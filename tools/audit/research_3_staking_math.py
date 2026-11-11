import os, sys, math
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round, GAME_RULES
from research_1_reverse_engineering import load_clean_corpus

sessions = load_clean_corpus()

# ==============================================================================
# PART A: EXACT ANALYTICAL & LINEAR PROGRAMMING THEORY OF STAKING LADDER (N steps)
# Under fair Matreshka table: p = 0.48 win, q = 0.52 loss, alpha = 0.98 net win.
# ==============================================================================

def analyze_theoretical_ladder(name, bets, p=0.48, alpha=0.98):
    N = len(bets)
    q = 1.0 - p
    cdt = 0
    turnover = 0.0
    cond_ev = 0.0
    uncond_ev = 0.0
    step_profits = []
    min_step_profit = float('inf')

    for k, b in enumerate(bets, 1):
        reach = q ** (k - 1)
        win_prob = reach * p
        net_win = alpha * b - cdt
        step_profits.append(net_win)
        min_step_profit = min(min_step_profit, net_win)
        cond_ev += win_prob * net_win
        turnover += reach * b
        cdt += b

    bust_prob = q ** N
    bust_loss = cdt
    expected_spins = sum(q ** k for k in range(N)) # approx E[steps per seq] = (1 - q^N)/p
    avg_len = (1.0 - q**N) / p
    uncond_ev = cond_ev - bust_prob * bust_loss
    cond_ev_per_spin = cond_ev / avg_len

    print(f"{name:<34} | B1={bets[0]:>5,d} | B_N={bets[-1]:>9,d} | MinPi={min_step_profit:>+7,.0f} | MaxPi={max(step_profits):>+8,.0f} | BustCost={bust_loss:>9,d} | CondEV/sp={cond_ev_per_spin:>+6.1f} | EV/Bust={cond_ev/(bust_prob*bust_loss):.3f}")
    return cond_ev, bust_loss, bust_prob, avg_len

def build_geom_ladder(b0, N, cap=1_000_000, x_min=2.025):
    bets = [b0]
    cdt = b0
    prev = b0
    for s in range(2, N + 1):
        rem = N - s + 1
        if rem == 1:
            bet = cap
        else:
            x = max(x_min, min(2.40, (cap / prev) ** (1.0 / rem)))
            geom = round(prev * x)
            tbb = math.ceil((cdt + b0) / 0.98)
            bet = max(tbb, geom)
            if rem == 2:
                # Strict 980k guard: cdt + bet + b_min/0.98 <= 980,000? Actually (cdt+bet)/0.98 <= 1_000_000 => cdt+bet <= 980_000!
                max_penult = 979000 - cdt
                if max_penult >= math.ceil(cdt / 0.98):
                    bet = min(bet, max_penult)
            bet = min(bet, cap)
        bets.append(bet)
        cdt += bet
        prev = bet
    return bets

def build_flat_tbb_ladder(b0, N, cap=1_000_000, front_boost=1.0, min_profit_tail=100):
    bets = [b0]
    cdt = b0
    for s in range(2, N + 1):
        if s == N:
            bet = cap
        else:
            target = b0 * front_boost if s <= 3 else max(min_profit_tail, min(b0, 975000))
            bet = math.ceil((cdt + target) / 0.98)
            if s == N - 1:
                max_pen = 979000 - cdt
                if max_pen >= math.ceil((cdt + 100)/0.98):
                    bet = min(bet, max_pen)
            bet = min(bet, cap)
        bets.append(bet)
        cdt += bet
    return bets

print("=== THEORETICAL COMPARISON UNDER FAIR RNG (p=0.48, alpha=0.98, Limit=1M) ===")
print(f"{'Ladder Strategy':<34} | {'B1':>8} | {'B_N':>13} | {'MinPi':>7} | {'MaxPi':>8} | {'BustCost':>9} | {'CondEV/sp':>9} | {'EV/Bust'}")
print("-" * 116)

for N in [8, 9, 10]:
    # Max possible uniform TBB B0 for N steps (where CDT_{N-1} <= 979,000 -> step N profits!)
    # Check grid for max B0 that keeps MinPi > 0
    best_max_b0 = 1000
    for cand in range(1000, 10000, 50):
        b_test = build_flat_tbb_ladder(cand, N, min_profit_tail=cand)
        # verify step N net > 0
        if 0.98 * b_test[-1] - sum(b_test[:-1]) > 0:
            best_max_b0 = cand

    analyze_theoretical_ladder(f"N={N} Low B0=1000 + High X", build_geom_ladder(1000, N))
    if best_max_b0 > 1200:
        mid_b0 = round((1000 + best_max_b0) / 2 / 50) * 50
        analyze_theoretical_ladder(f"N={N} Balanced Geom B0={mid_b0}", build_geom_ladder(mid_b0, N))
    analyze_theoretical_ladder(f"N={N} Max Uniform TBB B0={best_max_b0}", build_flat_tbb_ladder(best_max_b0, N, min_profit_tail=best_max_b0))
    # What if Step 1 is HUGE (front-loaded), and Steps 2..N only recover debt + 100 RUB (0 extra margin on tail)?
    max_front_b1 = 1000
    for cand in range(1000, 20000, 100):
        b_test = build_flat_tbb_ladder(cand, N, min_profit_tail=100)
        if 0.98 * b_test[-1] - sum(b_test[:-1]) > 0:
            max_front_b1 = cand
    analyze_theoretical_ladder(f"N={N} Front-Load Max B1={max_front_b1}, flat tail", build_flat_tbb_ladder(max_front_b1, N, min_profit_tail=100))
    print("-" * 116)


# ==============================================================================
# PART B: CLEAN FIXED EMPIRICAL SIMULATOR (FIXING THE 2 BUGS FOUND IN AUDIT 2!)
# Bugs fixed in research simulator to ensure ZERO fake windfalls or death-spirals:
# 1. terminalCap uses AVAILABLE_CYCLE_CAPITAL = (bankroll + cdt), NOT depleted bankroll!
#    Actual bet is still strictly <= bankroll (cannot bet more than wallet!).
# 2. On terminal step (or any partial-recovery step), NEVER bet more than min_tbb = ceil((cdt+base_bet)/0.98)
#    (never bet 1,000,000 RUB when cdt is only 128,929 RUB!).
# 3. Real 980k Horizon Guard: on penultimate step, enforce cdt + bet <= 979,000 whenever min_tbb allows,
#    OR compute max recoverable B0 cleanly!
# ==============================================================================

def clean_calc_bet(cdt, step, base_bet, target_steps, bankroll, prev_bet, geom_x_min=2.025, shape='GEOM'):
    base_bet = max(1000, base_bet)
    if cdt <= 0 or step <= 1:
        return min(base_bet, max(1000, bankroll))

    # Effective capital of the current progression cycle = remaining wallet + already staked CDT!
    cycle_capital = bankroll + cdt
    terminal_cap = max(1000, min(1_000_000, math.floor(cycle_capital / 1.90)))
    remaining = max(1, target_steps - step + 1)

    min_tbb = math.ceil((cdt + base_bet) / 0.98)

    if remaining == 1:
        # Terminal / overflow step: NEVER bet more than needed to recover cdt + base_bet!
        bet = min(min_tbb, terminal_cap, bankroll)
        return max(1000, js_round(bet))

    if shape == 'FLAT_TBB':
        bet = min_tbb
    elif shape == 'FRONT_BOOST':
        # Front-loaded: +30% extra profit on step 2, +15% on step 3, min TBB afterwards
        mult_profit = 1.30 if step == 2 else (1.15 if step == 3 else 0.25)
        bet = math.ceil((cdt + max(200, base_bet * mult_profit)) / 0.98)
    else:  # 'GEOM'
        prev_b = prev_bet if (prev_bet is not None and prev_bet > 0) else base_bet
        ratio = terminal_cap / max(1, prev_b)
        dyn_x = max(geom_x_min, min(2.40, math.pow(ratio, 1.0 / remaining)))
        geom_bet = js_round(prev_b * dyn_x)
        bet = max(min_tbb, geom_bet)

    # Strict 980k Horizon Guard on penultimate step (when table limit 1M is reachable)
    if remaining == 2 and terminal_cap >= 900_000:
        # Ensure after this loss, final step can win at <= terminal_cap!
        max_next_recoverable = math.floor(terminal_cap * 0.98) - cdt - 100
        if max_next_recoverable >= math.ceil((cdt + 100) / 0.98):
            bet = min(bet, max_next_recoverable)

    final_bet = max(1000, min(bet, 1_000_000, bankroll))
    return js_round(final_bet)

def eval_grid_across_corpus(config_fn, init_bank=3_000_000, lock_zebra=False, no_cooldown=False, stop_after_step=None):
    total_net = 0
    won = 0
    busted = 0
    worst_dd = 0
    max_st = 0
    limit_hits = 0
    dead_hits = 0
    total_spins = 0

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

        for outcome in s['outcomes']:
            if bank < 1000:
                busted += 1
                break
            if step == 1:
                seq_start_mode = curr_mode
                prev_bet = None

            bet_mode = 'ZEBRA' if (lock_zebra and seq_start_mode == 'ZEBRA') else curr_mode
            base_bet, t_steps, shape = config_fn(bet_mode, bank + cdt)

            if stop_after_step and step > stop_after_step:
                # Stop loss reset to Step 1
                cdt = 0
                step = 1
                prev_bet = None

            bet = clean_calc_bet(cdt, step, base_bet, t_steps, bank, prev_bet, shape=shape)
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
            if no_cooldown:
                raw = PrngDetectorMirror.detect_mode(history)
                if history[-10:].count('ZERO') >= 3 and raw == 'ZEBRA': raw = 'TRANSITION'
                curr_mode = raw
            else:
                curr_mode, prev_mode, s_danger, s_curr = PrngDetectorMirror.detect_mode_with_hysteresis(
                    history, prev_mode, curr_mode, s_danger, s_curr
                )

        sess_net = bank - init_bank
        total_net += sess_net
        if sess_net > 0: won += 1
        worst_dd = max(worst_dd, sess_dd)

    return {
        'net': total_net, 'won': won, 'n': len(sessions), 'busted': busted,
        'dd': worst_dd, 'max_st': max_st, 'lim': limit_hits, 'dead': dead_hits,
        'hr_270': total_net / max(1, total_spins) * 270.0
    }

print("\n=== EMPIRICAL CHECK AFTER FIXING BUGS #1 & #2 (ALL 27 CLEAN LIVE SESSIONS, 2,374 SPINS) ===")
print("Compare: Start Bankroll = 2,000,000 vs 3,500,000 (Strict No-Windfall Cap & Cycle-Capital Terminal Cap!)")

for init_b in [2_000_000, 3_500_000]:
    print(f"\n--- Init Bankroll: {init_b:,} RUB ---")
    print(f"{'Configuration':<48} | {'Total Net':>11} | {'RUB/hr':>9} | {'Won':>5} | {'Worst DD':>10} | {'St':>2} | {'Lim':>3} | {'Dead'}")
    print("-" * 108)
    configs = [
        ("v12.4 Matrix (Z=3000/N9, T=1500/N10, D=1000/N10)", lambda m, b: (3000,9,'GEOM') if (m=='ZEBRA' and b>=3e6) else ((2000,9,'GEOM') if m=='ZEBRA' else ((1500 if b>=3e6 else 1200,10,'GEOM') if m=='TRANSITION' else (1000,10,'GEOM'))), False),
        ("v12.4 Matrix + ZEBRA LOCK",                        lambda m, b: (3000,9,'GEOM') if (m=='ZEBRA' and b>=3e6) else ((2000,9,'GEOM') if m=='ZEBRA' else ((1500 if b>=3e6 else 1200,10,'GEOM') if m=='TRANSITION' else (1000,10,'GEOM'))), True),
        ("Low Base / High X (All modes B0=1000, N=10, GEOM)",lambda m, b: (1000,10,'GEOM'), False),
        ("Max Uniform TBB 10-st (All modes B0=1700, N=10)",  lambda m, b: (1700,10,'FLAT_TBB'), False),
        ("Mode-Optimal Geom (Z=3500/N9, T=1700/N10, D=1000)",lambda m, b: (3500,9,'GEOM') if (m=='ZEBRA' and b>=3e6) else ((2500,9,'GEOM') if m=='ZEBRA' else ((1700 if b>=3e6 else 1400,10,'GEOM') if m=='TRANSITION' else (1000,10,'GEOM'))), False),
        ("Mode-Optimal Geom + ZEBRA LOCK",                   lambda m, b: (3500,9,'GEOM') if (m=='ZEBRA' and b>=3e6) else ((2500,9,'GEOM') if m=='ZEBRA' else ((1700 if b>=3e6 else 1400,10,'GEOM') if m=='TRANSITION' else (1000,10,'GEOM'))), True),
        ("10-Step Safe High-Z (Z=3500/N9, T=1500/N10, D=1000) FLAT", lambda m, b: (3500,9,'FLAT_TBB') if (m=='ZEBRA' and b>=3e6) else ((2500,9,'FLAT_TBB') if m=='ZEBRA' else ((1500 if b>=3e6 else 1200,10,'FLAT_TBB') if m=='TRANSITION' else (1000,10,'FLAT_TBB'))), False),
        ("Aggressive 9-st All (Z=3500, T=2500, D=1500, N=9)", lambda m, b: (3500,9,'GEOM') if m=='ZEBRA' else ((2500,9,'GEOM') if m=='TRANSITION' else (1500,9,'GEOM')), False),
        ("SHIELD 10-st (Z=2000, T=1200, D=1000, N=10)",      lambda m, b: (2000,10,'GEOM') if m=='ZEBRA' else ((1200,10,'GEOM') if m=='TRANSITION' else (1000,10,'GEOM')), False),
    ]
    for label, fn, lz in configs:
        r = eval_grid_across_corpus(fn, init_b, lock_zebra=lz)
        print(f"{label[:48]:<48} | {r['net']:>+11,d} | {r['hr_270']:>+9,.0f} | {r['won']:>2}/{r['n']:<2} | {r['dd']:>10,d} | {r['max_st']:>2} | {r['lim']:>3} | {r['dead']}")
