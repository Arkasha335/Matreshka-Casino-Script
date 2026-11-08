import json
import sys
import numpy as np

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Projects\MTCasinoScript\tools\audit\normalized_spins.json", "r", encoding="utf-8") as f:
    spins = json.load(f)

# Group by session so we don't cross session boundaries!
sessions = {}
for s in spins:
    sid = s["session_id"]
    if sid not in sessions:
        sessions[sid] = []
    sessions[sid].append(s)

print(f"Number of distinct sessions: {len(sessions)}")

# Session summaries
print("\n--- Session Performance Breakdown ---")
print(f"{'Session ID':<30} | {'Spins':<6} | {'Profit (₽)':<14} | {'MaxDD (₽)':<12} | {'Zero %':<8} | {'Win %':<8}")
print("-" * 88)

total_profit_all = 0
total_spins_all = 0
total_zero_all = 0
total_wins_all = 0

for sid, s_list in sessions.items():
    spins_cnt = len(s_list)
    initial_bal = s_list[0]["balance"]
    last_s = s_list[-1]
    final_bal = last_s["balance"] + (last_s["expected_delta"] if last_s["actual_next_balance_delta"] is None else 0)
    profit = final_bal - initial_bal
    
    # Calculate Max Drawdown from equity curve
    eq = initial_bal
    peak = initial_bal
    max_dd = 0
    for s in s_list:
        eq += s["expected_delta"]
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
            
    zeros = sum(1 for s in s_list if s["outcome"] == "ZERO")
    wins = sum(1 for s in s_list if s["is_win"])
    
    total_profit_all += profit
    total_spins_all += spins_cnt
    total_zero_all += zeros
    total_wins_all += wins
    
    print(f"{sid:<30} | {spins_cnt:<6} | {profit:>14,.2f} | {max_dd:>12,.2f} | {zeros/spins_cnt*100:>7.1f}% | {wins/spins_cnt*100:>7.1f}%")

print("-" * 88)
print(f"{'TOTAL / OVERALL':<30} | {total_spins_all:<6} | {total_profit_all:>14,.2f} | {'-':<12} | {total_zero_all/total_spins_all*100:>7.1f}% | {total_wins_all/total_spins_all*100:>7.1f}%")

# Markov transition matrix (within sessions)
# States: RED, BLACK, ZERO
states = ["RED", "BLACK", "ZERO"]
state_to_idx = {st: i for i, st in enumerate(states)}
trans_counts = np.zeros((3, 3), dtype=int)

for sid, s_list in sessions.items():
    for i in range(len(s_list) - 1):
        s_from = s_list[i]["outcome"]
        s_to = s_list[i+1]["outcome"]
        trans_counts[state_to_idx[s_from], state_to_idx[s_to]] += 1

print("\n--- Empirical Markov Transition Matrix P(Next | Current) ---")
print(f"{'From \\ To':<12} | {'RED':<10} | {'BLACK':<10} | {'ZERO':<10} | Total")
print("-" * 55)
for i, s_from in enumerate(states):
    row_sum = np.sum(trans_counts[i])
    probs = trans_counts[i] / row_sum if row_sum > 0 else np.zeros(3)
    print(f"{s_from:<12} | {probs[0]*100:>8.2f}% | {probs[1]*100:>8.2f}% | {probs[2]*100:>8.2f}% | {row_sum}")

print("\nTheoretical European Roulette: RED -> 48.65% RED, 48.65% BLACK, 2.70% ZERO")
print("Theoretical American Roulette: RED -> 47.37% RED, 47.37% BLACK, 5.26% ZERO")

# Exact streak continuation analysis
# For any streak of color C of length k, what is P(C continues | streak length k)?
print("\n--- Exact Conditional Streak Continuation Probability ---")
print("At streak of length k, does color continue (C) or switch/zero?")
for k in range(1, 9):
    continue_cnt = 0
    flip_cnt = 0
    zero_cnt = 0
    
    for sid, s_list in sessions.items():
        curr_col = None
        streak_len = 0
        for s in s_list:
            out = s["outcome"]
            if out == "ZERO":
                if streak_len == k:
                    zero_cnt += 1
                curr_col = None
                streak_len = 0
            else:
                if out == curr_col:
                    streak_len += 1
                    if streak_len == k + 1:
                        continue_cnt += 1
                else:
                    if streak_len == k:
                        flip_cnt += 1
                    curr_col = out
                    streak_len = 1
                    
    total = continue_cnt + flip_cnt + zero_cnt
    if total > 0:
        p_cont = continue_cnt / total
        p_flip = flip_cnt / total
        p_zero = zero_cnt / total
        print(f"  Streak k = {k}: N = {total:3d} | Continue = {continue_cnt:3d} ({p_cont*100:5.1f}%) | Switch = {flip_cnt:3d} ({p_flip*100:5.1f}%) | Zero = {zero_cnt:2d} ({p_zero*100:4.1f}%)")
