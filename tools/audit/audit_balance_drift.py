import json
import math
import os
import sys

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)

logs = d["logs"]
init_b = d["metadata"]["initialBankroll"]
curr_b = d["metadata"]["currentBankroll"]

print(f"Initial bankroll: {init_b:,}")
print(f"Current bankroll in log: {curr_b:,}")
print(f"User reported real game balance end: ...505 ₽ (e.g. 5,041,505)")
print(f"Reported diff: 505 - 73 = +432 rubles in game vs script!")

# Check every single log entry
b = init_b
for i, e in enumerate(logs):
    b += e["net_profit"]
    if b != e["current_balance"]:
        print(f"Diff at spin {i+1}: b={b}, logged={e['current_balance']}")

print(f"Cumulative check passed: final = {b}")

# Let's see what happens to bet amounts:
# Are bets entered by user rounded to nearest 10 or 100 in the game?
# What if the user types bets, but the game truncates or rounds?
# Or what if casino pays:
# Let's inspect all 92 winning bets in detail:
wins = [e for e in logs if e["is_win"]]
losses = [e for e in logs if not e["is_win"]]
print(f"Wins count: {len(wins)}, Losses count: {len(losses)}")

# What if winning payout is not bet * 0.98?
# What if winning payout is:
# Win payout = bet * 2
# Wait! In roulette, when you win, you get your bet back + profit.
# What if commission is 2% of PROFIT, but in PAWN/GTA it's computed as:
# floor(bet * 0.98) or floor(bet * 98 / 100)
# But what if on LOSS there's no commission? Loss is exactly -bet.
# Wait! If the game has MORE balance (+432), that means:
# Either WIN net profit was higher in the game than the script calculated,
# OR LOSS was less than the script subtracted!
# Could loss be less? No, when you bet X, you lose X.
# Could win profit be higher?
# 432 / 92 wins = ~4.7 rubles per win!
print(f"Average drift per win: 432 / {len(wins)} = {432 / len(wins):.2f} ₽ per win!")
print(f"Average drift per spin: 432 / {len(logs)} = {432 / len(logs):.2f} ₽ per spin!")

# Let's check the base bets:
# When base bet is placed (step 1):
# In TURBO >= 3M:
# ZEBRA b0 = 8500. 8500 * 0.98 = 8330.
# Is 8500 * 0.98 exact integer? 8500 * 0.98 = 8330.0! Exact!
# TRANSITION b0 = 5000. 5000 * 0.98 = 4900.0! Exact!
# DANGER b0 = 2000. 2000 * 0.98 = 1960.0! Exact!
# So on step 1, 0.98 * bet is ALWAYS an exact integer with 0 fraction!
step1_wins = [e for e in wins if e["current_step"] == 1]
step_gt1_wins = [e for e in wins if e["current_step"] > 1]
print(f"Step 1 wins: {len(step1_wins)}")
print(f"Step > 1 wins: {len(step_gt1_wins)}")

# Check fractional parts for step > 1:
for e in step_gt1_wins:
    bet = e["current_bet"]
    exact_profit = bet * 0.98
    print(f"  step {e['current_step']} bet={bet:7d}: exact_profit={exact_profit:.2f}, logged_net={e['net_profit']}")
