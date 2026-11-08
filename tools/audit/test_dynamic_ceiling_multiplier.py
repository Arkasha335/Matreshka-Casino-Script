import math
from simulate_terminal_strategies import MPDPredictor, sessions

def dynamic_ceiling_multiplier_bet(step, cdt, bank, init_bank, profile='APEX_IDEAL'):
    # Determine target step capacity N based on profile
    if profile == 'TURBO_HARVEST':
        target_steps = 9
        base_b0 = 1500
    elif profile == 'SHIELD_CONSERVATIVE':
        target_steps = 11
        base_b0 = 800
    else: # APEX_IDEAL
        target_steps = 10
        base_b0 = 1200
        
    # Scale base_b0 if bankroll is small
    if bank < 2_000_000:
        base_b0 = max(500, round(base_b0 * (bank / 2_000_000)))
        
    if step <= 1 or cdt <= 0:
        return base_b0
        
    # Terminal ceiling that bankroll and table limit can support
    # Total sum of geometric progression is roughly 1.9 * B_terminal
    terminal_cap = min(1_000_000, round(bank / 1.92))
    
    # Remaining steps including this one:
    remaining_steps = max(1, target_steps - step + 1)
    
    if remaining_steps == 1:
        # This is the terminal step: snap to terminal cap!
        return min(terminal_cap, bank)
        
    # Minimum bet needed to cover debt with 2% tax + base profit
    min_tbb = (cdt + base_b0) / 0.98
    
    # We want a smooth multiplier X from min_tbb to terminal_cap in remaining_steps - 1 steps:
    # X^(remaining_steps - 1) = terminal_cap / min_tbb
    if terminal_cap > min_tbb:
        ratio = terminal_cap / min_tbb
        power = 1.0 / (remaining_steps - 1)
        x = ratio ** power
        
        # If X is too small (below 2.0204), it wouldn't cover 2% tax in future steps
        # If X is too large (e.g. > 2.4), we should clamp it
        x = max(2.03, min(2.40, x))
        
        # Next bet is min_tbb, or if step > 2 we can follow X
        bet = round(min_tbb)
    else:
        # We are already at or near the terminal cap
        bet = min(terminal_cap, bank)
        
    return min(1_000_000, min(bank, max(base_b0, bet)))

print("Testing dynamic ceiling multiplier bet function...")
for step in range(1, 12):
    b0 = 1200
    # Simulate a losing streak
    cdt = 0
    cur_bet = b0
    for s in range(1, step):
        cdt += cur_bet
        cur_bet = dynamic_ceiling_multiplier_bet(s+1, cdt, 3_800_000, 3_800_000)
    print(f"Step {step:2d} | CDT: {cdt:8,d} | Bet: {cur_bet:8,d} | Table %: {cur_bet/10000:.1f}%")
