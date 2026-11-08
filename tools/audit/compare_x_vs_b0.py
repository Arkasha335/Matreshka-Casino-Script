import json
import glob
import os
import math
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Compare A vs B vs C mathematically:
# Table limit: 1,000,000 RUB
# Tax on win: 2% (payout = 0.98 * bet)
# When bet loses, cumulative deficit CDT increases.
# To recover all previous losses and win target net profit W:
# Bet_k = (CDT_k + W) / 0.98

print("=== MATHEMATICAL ANALYSIS: BASE BET (B0) VS MULTIPLIER (X) ===")
print("Objective: Maximize Net Profit/Hour while staying below 1,000,000 RUB Table Limit\n")

# Let's trace consecutive losses k = 1 to 10 for different configurations:
configs = [
    {"name": "Config A: High B0 (15,000), Low X (2.05)", "b0": 15000, "growth": 2.05, "sniper": 1.0},
    {"name": "Config B: Med B0 (5,000), Med X (2.15)",   "b0": 5000,  "growth": 2.15, "sniper": 1.1},
    {"name": "Config C: Low B0 (2,500), High X (2.35)",  "b0": 2500,  "growth": 2.35, "sniper": 1.3},
    {"name": "Config D: Smart Dynamic (B0 3,000, Adaptive X)", "b0": 3000, "adaptive": True}
]

for cfg in configs:
    print(f"--- {cfg['name']} ---")
    print(f"{'Step':<5} | {'Bet (₽)':<12} | {'Cumulative Loss':<18} | {'Net Win Profit (₽)':<20} | {'Status'}")
    print("-" * 75)
    
    b0 = cfg["b0"]
    cdt = 0
    cur_bet = b0
    
    for step in range(1, 12):
        if cfg.get("adaptive"):
            # Adaptive: high profit on steps 1-2, compressed growth on steps 4+
            if cdt <= 0:
                cur_bet = b0
            else:
                tbb = round((cdt + b0) / 0.98)
                if step == 2:
                    cur_bet = round(tbb * 1.2) # extra boost
                elif step == 3:
                    cur_bet = round(tbb * 1.1)
                elif step >= 6:
                    cur_bet = tbb # pure exact recovery, no excess multiplier!
                else:
                    cur_bet = tbb
        else:
            if cdt <= 0:
                cur_bet = b0
            else:
                tbb = round((cdt + b0) / 0.98)
                geom = round(b0 * (cfg["growth"] ** (step - 1)))
                if cdt > b0 * 2 and step >= 2 and cfg["sniper"] > 1.0:
                    cur_bet = max(round(tbb * cfg["sniper"]), geom)
                else:
                    cur_bet = max(tbb, geom)
                    
        is_limit = cur_bet >= 1000000
        cur_bet = min(1000000, cur_bet)
        net_profit_on_win = (cur_bet * 0.98) - cdt
        
        status = "TABLE LIMIT!" if is_limit else "OK"
        print(f"{step:<5} | {cur_bet:>12,d} | {cdt:>18,d} | {net_profit_on_win:>20,.0f} | {status}")
        
        cdt += cur_bet
        if is_limit:
            break
    print("-" * 75 + "\n")
