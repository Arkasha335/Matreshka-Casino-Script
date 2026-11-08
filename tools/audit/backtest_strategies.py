import json
import sys
import numpy as np

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Projects\MTCasinoScript\tools\audit\normalized_spins.json", "r", encoding="utf-8") as f:
    spins = json.load(f)

# Backtest on real 984 spins
# Compare:
# Strategy 0: Original actual results in log (lost 374,867 RUB)
# Strategy 1: Fixed Flat Betting (e.g. 1,000 RUB per spin)
# Strategy 2: Capped Conservative Fibonacci/d'Alembert with Hard Stop-Loss (15%)
# Strategy 3: Fractional Kelly with Zero-Cluster Freeze (Skip 3 spins after Zero)

print("--- Backtest on Exact Historical 984 Spins ---")

# 1. Flat Betting 2,000 RUB
bal = 1000000
peak = bal
max_dd = 0
for s in spins:
    bet = 2000
    is_win = s["is_win"]
    delta = bet * 0.98 if is_win else -bet
    bal += delta
    if bal > peak:
        peak = bal
    dd = peak - bal
    if dd > max_dd:
        max_dd = dd

print(f"Flat Bet (2,000 RUB): Final Profit = {bal - 1000000:,.2f} RUB, MaxDD = {max_dd:,.2f} RUB")

# 2. Zero-Freeze Filter: Skip 3 spins immediately after ANY Zero
bal = 1000000
peak = bal
max_dd = 0
skip_spins = 0
spins_played = 0
for s in spins:
    if skip_spins > 0:
        skip_spins -= 1
        if s["outcome"] == "ZERO":
            skip_spins = 3
        continue
        
    bet = 2000
    spins_played += 1
    is_win = s["is_win"]
    delta = bet * 0.98 if is_win else -bet
    bal += delta
    if bal > peak:
        peak = bal
    dd = peak - bal
    if dd > max_dd:
        max_dd = dd
        
    if s["outcome"] == "ZERO":
        skip_spins = 3

print(f"Zero-Freeze (Skip 3 spins after Zero): Spins Played = {spins_played}, Profit = {bal - 1000000:,.2f} RUB, MaxDD = {max_dd:,.2f} RUB")
