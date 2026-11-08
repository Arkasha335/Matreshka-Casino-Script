import json
import math
import sys
import numpy as np

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def calculate_bet_current(cdt, step, base_bet, growth_factor, sniper_mult, bankroll):
    if cdt <= 0:
        return base_bet
    tbb = (cdt + base_bet) / 0.98
    geom = base_bet * (growth_factor ** (step - 1))
    if cdt > base_bet * 2 and step >= 2:
        sniper_bet = tbb * sniper_mult
        bet = sniper_bet if sniper_bet > geom else geom
    else:
        bet = tbb if tbb > geom else geom
    if bet < base_bet:
        bet = base_bet
    if bet > 1000000:
        bet = 1000000
    if bet > bankroll:
        bet = bankroll
    return bet

def get_engine_params_current(bankroll):
    min_b = 500000
    max_b = 6500000
    clamped = max(min_b, min(bankroll, max_b))
    ratio = (clamped - min_b) / (max_b - min_b)
    
    full_base = 1000 + ratio * (4000 - 1000)
    full_growth = 2.2 + ratio * (2.5 - 2.2)
    sniper_mult = 1.6
    return full_base, full_growth, sniper_mult

P_WIN = 0.4807
WIN_PAYOUT = 0.98

print("================================================================================", flush=True)
print("             MONTE CARLO SIMULATION OF CURRENT STRATEGY (N = 2,500 RUNS)        ", flush=True)
print("================================================================================\n", flush=True)

spin_horizons = [100, 250, 500, 1000, 2000]
initial_bankrolls = [500000, 1000000, 3000000, 6500000]
num_sims = 2500

for b0 in initial_bankrolls:
    base_b, growth_f, sn_m = get_engine_params_current(b0)
    print(f"\n--- Initial Bankroll: {b0:,.0f} RUB (Base Bet: {base_b:,.0f} RUB, Growth: x{growth_f:.2f}) ---", flush=True)
    print(f"{'Spins':<7} | {'RoR (%)':<8} | {'Median Profit':<14} | {'Mean Profit':<14} | {'Median MaxDD':<14} | {'95% MaxDD':<14}", flush=True)
    print("-" * 80, flush=True)
    
    for max_spins in spin_horizons:
        ruined = 0
        max_drawdowns = []
        final_profits = []
        
        np.random.seed(42)
        # Pre-generate random matrix of shape (num_sims, max_spins)
        random_wins = (np.random.random((num_sims, max_spins)) < P_WIN)
        
        for sim in range(num_sims):
            bal = float(b0)
            peak = float(b0)
            max_dd = 0.0
            cdt = 0.0
            step = 1
            
            sim_wins = random_wins[sim]
            
            for s in range(max_spins):
                bet = calculate_bet_current(cdt, step, base_b, growth_f, sn_m, bal)
                
                if sim_wins[s]:
                    profit = bet * WIN_PAYOUT
                    bal += profit
                    cdt = max(0.0, cdt - profit)
                    if cdt < 10.0:
                        cdt = 0.0
                        step = 1
                else:
                    bal -= bet
                    cdt += bet
                    step += 1
                
                if bal > peak:
                    peak = bal
                dd = peak - bal
                if dd > max_dd:
                    max_dd = dd
                    
                if bal <= 0:
                    ruined += 1
                    break
                    
            max_drawdowns.append(max_dd)
            final_profits.append(bal - b0)
            
        ror = (ruined / num_sims) * 100.0
        median_profit = np.median(final_profits)
        mean_profit = np.mean(final_profits)
        median_dd = np.median(max_drawdowns)
        p95_dd = np.percentile(max_drawdowns, 95)
        
        print(f"{max_spins:<7d} | {ror:>7.1f}% | {median_profit:>14,.0f} | {mean_profit:>14,.0f} | {median_dd:>14,.0f} | {p95_dd:>14,.0f}", flush=True)
