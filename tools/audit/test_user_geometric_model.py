import math

def solve_dynamic_multiplier(b0, target_steps, limit=1_000_000, tax=0.02):
    # We want B_N = b0 * X^(N-1) = limit
    # X = (limit / b0) ** (1 / (target_steps - 1))
    x = (limit / b0) ** (1.0 / (target_steps - 1))
    
    # Check minimum required multiplier to cover 2% tax
    min_x = 1.0 + 1.0 / (1.0 - tax) # ~ 2.020408
    
    bets = []
    cdt = 0
    profits = []
    for step in range(1, target_steps + 1):
        bet = round(b0 * (x ** (step - 1)))
        if step == target_steps:
            bet = limit # exact terminal snap
        bets.append(bet)
        profit_on_win = bet * (1.0 - tax) - cdt
        profits.append(round(profit_on_win))
        cdt += bet
        
    return x, bets, profits, cdt

print("--- Dynamic Constant Multiplier Ladders ---")
for n in [9, 10, 11]:
    for b in [1000, 1200, 1500, 1600, 2000]:
        x, bets, profits, total = solve_dynamic_multiplier(b, n)
        # Check if all profits are positive
        all_pos = all(p > 0 for p in profits)
        if all_pos and bets[-1] <= 1_000_000:
            print(f"N={n:2d} | B0={b:5d} -> X={x:.4f} | Total Bankroll={total:9,d} | Step {n-1}: {bets[-2]:7,d} (Win Profit: +{profits[-2]:6,d}) | Step {n}: {bets[-1]:7,d} (Win Profit: +{profits[-1]:7,d})")
