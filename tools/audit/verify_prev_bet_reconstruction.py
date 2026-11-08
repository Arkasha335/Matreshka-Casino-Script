import os, sys, math, json, glob
sys.path.append(os.path.dirname(__file__))
from simulate_terminal_strategies import MPDPredictor
from test_suite_v12_4 import get_calibrated_base_bet, calculate_bet_v12_4

def calc_bet_reconstruct(step, cdt, mode, profile, bankroll):
    base_b0, target_steps = get_calibrated_base_bet(profile, mode, bankroll)
    terminal_cap = min(1_000_000, math.floor(bankroll / 1.90))
    terminal_cap = max(1000, terminal_cap)
    
    if step <= 1 or cdt <= 0:
        return max(1000, min(base_b0, bankroll))
        
    remaining = max(1, target_steps - step + 1)
    if remaining == 1:
        return max(1000, min(terminal_cap, bankroll))
        
    # Exponent for full ladder
    growth_x = math.pow(terminal_cap / base_b0, 1.0 / (target_steps - 1))
    prev_b = round(base_b0 * math.pow(growth_x, step - 2))
    
    ratio = terminal_cap / max(1, prev_b)
    dynamic_x = max(2.025, min(2.40, math.pow(ratio, 1.0 / remaining)))
    geom_bet = round(prev_b * dynamic_x)
    
    min_tbb = math.ceil((cdt + base_b0) / 0.98)
    bet = max(min_tbb, geom_bet)
    
    if remaining == 2 and terminal_cap >= 900_000:
        max_safe = max(min_tbb, 975_000 - cdt)
        bet = min(bet, max_safe)
        
    final_bet = max(1000, min(bet, 1_000_000, bankroll))
    return int(round(final_bet))

# Check difference on synthetic ladder
for mode in ['ZEBRA', 'TRANSITION', 'DANGER']:
    print(f"=== Testing Mode = {mode} ===")
    cdt = 0
    prev_b = 0
    for s in range(1, 11):
        b_direct = calculate_bet_v12_4(s, cdt, mode, 'APEX_IDEAL', 3_800_000, prev_b if s > 1 else None)
        b_recon = calc_bet_reconstruct(s, cdt, mode, 'APEX_IDEAL', 3_800_000)
        print(f"Step {s:2d} | Direct: {b_direct:7,d} | Recon: {b_recon:7,d} | Diff: {b_direct - b_recon:5d} | CDT: {cdt:9,d}")
        cdt += b_direct
        prev_b = b_direct

