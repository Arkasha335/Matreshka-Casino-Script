import math
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

print("=== MATHEMATICAL FRONTIER: BASE BET (B0) vs GROWTH MULTIPLIER (X) ===")
print("Table limit L = 1,000,000 RUB. P(Loss) q = 0.52 (52%)\n")

print(f"{'Base Bet (B0)':<14} | {'Growth X':<10} | {'Steps to 1M (S)':<16} | {'P(Exhaust) q^S':<16} | {'Avg Spins to Fail (1/q^S)':<26}")
print("-" * 88)

base_bets = [1000, 1500, 2000, 2500, 3000, 5000, 10000, 26000]
growth_factors = [2.0, 2.1, 2.2, 2.3, 2.5]

for b0 in base_bets:
    for x in growth_factors:
        # Calculate steps until bet >= 1,000,000
        step = 1
        cur_bet = b0
        cum_loss = 0
        while cur_bet < 1000000 and step < 25:
            cum_loss += cur_bet
            step += 1
            # TBB with 2% tax
            tbb = round((cum_loss + b0) / 0.98)
            geom = round(b0 * (x ** (step - 1)))
            cur_bet = max(tbb, geom)
            
        steps_to_limit = step
        q_s = (0.52) ** steps_to_limit
        spins_to_ruin = 1.0 / q_s if q_s > 0 else float('inf')
        
        if x in [2.0, 2.2, 2.5]:
            print(f"{b0:>10,d} ₽  | {x:>8.1f}x  | {steps_to_limit:>14d}   | {q_s*100:>14.4f}% | {spins_to_ruin:>24,.0f} spins")
    print("-" * 88)
