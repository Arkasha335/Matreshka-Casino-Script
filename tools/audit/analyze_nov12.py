import json
import math
import os
import statistics
import sys

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)

logs = d["logs"]
meta = d["metadata"]

total_spins = len(logs)
red_count = sum(1 for e in logs if e["input_result"] == "RED")
black_count = sum(1 for e in logs if e["input_result"] == "BLACK")
zero_count = sum(1 for e in logs if e["input_result"] == "ZERO")
wins = sum(1 for e in logs if e.get("is_win"))
losses = total_spins - wins
non_zero_spins = total_spins - zero_count

print(f"Total spins: {total_spins}")
print(f"Red: {red_count} ({red_count / total_spins * 100:.2f}%)")
print(f"Black: {black_count} ({black_count / total_spins * 100:.2f}%)")
print(f"Zero: {zero_count} ({zero_count / total_spins * 100:.2f}%)")
print(f"Wins: {wins} ({wins / total_spins * 100:.2f}%)")
print(f"Non-Zero WinRate: {wins / non_zero_spins * 100:.2f}% (Wins: {wins}/{non_zero_spins})")

w1 = logs[:100]
w2 = logs[100:]
w1_wins = sum(1 for e in w1 if e.get("is_win"))
w2_wins = sum(1 for e in w2 if e.get("is_win"))
w1_nz = sum(1 for e in w1 if e["input_result"] != "ZERO")
w2_nz = sum(1 for e in w2 if e["input_result"] != "ZERO")
print(f"First 100 spins winrate: {w1_wins / len(w1) * 100:.2f}% (Non-Zero: {w1_wins / w1_nz * 100:.2f}%)")
print(f"Last 99 spins winrate: {w2_wins / len(w2) * 100:.2f}% (Non-Zero: {w2_wins / w2_nz * 100:.2f}%)")

bets = [e["current_bet"] for e in logs]
steps = [e["current_step"] for e in logs]
max_bet = max(bets)
max_step = max(steps)
print(f"Max bet: {max_bet:,} ₽")
print(f"Max step: {max_step}")
high_bets = [(i, e) for i, e in enumerate(logs) if e["current_bet"] >= 100000]
print(f"Bets >= 100k count: {len(high_bets)}")
for i, e in high_bets:
    print(
        f"  spin {i + 1:3d}: bet={e['current_bet']:8,d} step={e['current_step']} "
        f"mode={e.get('current_mode')} pred={e['recommended_action']:5s} "
        f"out={e['input_result']:5s} win={e['is_win']} bal={e['current_balance']:9,d}"
    )

dur_h = meta["durationMs"] / 3_600_000.0
hourly_profit = meta["totalProfit"] / dur_h if dur_h > 0 else 0
print(f"Duration: {dur_h:.2f} h ({meta['durationMs'] / 60000:.1f} min)")
print(f"Profit: {meta['totalProfit']:+,} ₽")
print(f"Hourly rate: {hourly_profit:+,.0f} ₽/h")
print(f"Max Drawdown recorded: {meta['maxDrawdown']:,} ₽")
