import json
from simulate_terminal_strategies import MPDPredictor, sessions

def run_test(name, strategy_fn, initial_bankroll=3_806_838):
    total_net = 0
    total_wins = 0
    total_spins = 0
    sessions_won = 0
    max_step_seen = 0
    limit_hits = 0
    total_drawdown = 0

    for sess in sessions:
        pred = MPDPredictor()
        bank = initial_bankroll
        cdt = 0
        step = 1
        sess_max_step = 0
        peak = bank
        max_dd = 0
        
        for outcome in sess['outcomes']:
            rec = pred.get_recommendation()
            bet = strategy_fn(step, cdt, bank, initial_bankroll)
            
            # Check table limit
            if bet > 1_000_000:
                limit_hits += 1
                bet = 1_000_000
            
            sess_max_step = max(sess_max_step, step)
            total_spins += 1
            
            if outcome == rec:
                # Win (2% tax)
                win_amt = bet * 1.98
                net = win_amt - bet
                bank += net
                cdt = 0
                step = 1
                total_wins += 1
            else:
                # Loss
                bank -= bet
                cdt += bet
                step += 1
                
            pred.add_result(outcome)
            peak = max(peak, bank)
            max_dd = max(max_dd, peak - bank)
            
        max_step_seen = max(max_step_seen, sess_max_step)
        profit = bank - initial_bankroll
        total_net += profit
        total_drawdown = max(total_drawdown, max_dd)
        if profit > 0:
            sessions_won += 1

    print(f"Strategy: {name:35s} | Net Profit: {total_net:12,.2f} RUB | Won: {sessions_won:2d}/{len(sessions)} | MaxStep: {max_step_seen} | MaxDD: {total_drawdown:9,.0f} RUB | LimitHits: {limit_hits}")

print("\n--- Comparative Evaluation of Dynamic Terminal Strategies ---")

# Strategy 1: Old TURBO_HARVEST (with growthFactor=2.20)
def strat_old_turbo(step, cdt, bank, init_bank):
    b0 = round(2500 + (bank - 500_000) / (6_500_000 - 500_000) * (5500 - 2500))
    if cdt <= 0: return b0
    tbb = round((cdt + b0) / 0.98)
    if step == 2: bet = round(tbb * 1.25)
    elif step == 3: bet = round(tbb * 1.15)
    else: bet = tbb
    geom = round(b0 * (2.20 ** (step - 1)))
    return min(1_000_000, max(bet, geom))

# Strategy 2: User's Theory - Dynamic Terminal Boundary APEX (10 Steps, B0=1765, Minimal X, Terminal Snap)
def strat_terminal_apex_10(step, cdt, bank, init_bank):
    # Dynamic B0 based on bankroll: guarantees 10 steps up to 1,000,000 ceiling
    max_b0_for_10 = 1765
    b0 = min(max_b0_for_10, max(1000, round(bank / 2_000_000 * max_b0_for_10)))
    if cdt <= 0: return b0
    
    tbb = round((cdt + b0) / 0.98)
    
    # Calculate how many steps remaining
    # If the NEXT step after this one would exceed 1,000,000 or bankroll:
    # Then THIS bet is either penultimate or terminal!
    next_cdt = cdt + tbb
    next_tbb = (next_cdt + b0) / 0.98
    
    if tbb >= 1_000_000 or next_tbb > 1_000_000 or (next_cdt + next_tbb) > bank:
        # We are on the final step! Snap to 1,000,000 ceiling!
        return min(1_000_000, bank)
    
    # Steps 1 to N-1: use pure minimal TBB (or slight 1.05 boost on step 2)
    if step == 2:
        return round(tbb * 1.10)
    return tbb

# Strategy 3: Dynamic Terminal Boundary TURBO (9 Steps, B0=3565, Minimal X, Terminal Snap)
def strat_terminal_turbo_9(step, cdt, bank, init_bank):
    # Dynamic B0 based on bankroll: guarantees 9 steps up to 1,000,000 ceiling
    max_b0_for_9 = 3565
    b0 = min(max_b0_for_9, max(1500, round(bank / 2_000_000 * max_b0_for_9)))
    if cdt <= 0: return b0
    
    tbb = round((cdt + b0) / 0.98)
    
    next_cdt = cdt + tbb
    next_tbb = (next_cdt + b0) / 0.98
    
    if tbb >= 1_000_000 or next_tbb > 1_000_000 or (next_cdt + next_tbb) > bank:
        # Final step! Snap to ceiling
        return min(1_000_000, bank)
        
    if step == 2:
        return round(tbb * 1.10)
    return tbb

# Strategy 4: Dynamic Hybrid (9 steps in ZEBRA, 10 steps in TRANSITION/DANGER)
def strat_dynamic_hybrid(step, cdt, bank, init_bank):
    # In normal conditions: 9 steps (B0 ~ 3000)
    # If step >= 4 or CDT is high: switch to pure minimal recovery
    b0 = 2500
    if cdt <= 0: return b0
    tbb = round((cdt + b0) / 0.98)
    if step == 2: return round(tbb * 1.10)
    next_cdt = cdt + tbb
    next_tbb = (next_cdt + b0) / 0.98
    if next_tbb > 1_000_000:
        return min(1_000_000, bank)
    return tbb

run_test("Old Turbo Harvest (growth=2.20)", strat_old_turbo)
run_test("Terminal APEX 10-Step (B0=1765)", strat_terminal_apex_10)
run_test("Terminal TURBO 9-Step (B0=3565)", strat_terminal_turbo_9)
run_test("Dynamic Hybrid (B0=2500)", strat_dynamic_hybrid)
