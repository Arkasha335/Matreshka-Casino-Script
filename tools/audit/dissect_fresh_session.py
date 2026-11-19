"""
Dissect fresh session from 17.11.2026 (session_20261117_165453.jsonl)
"""
import json
import math
import numpy as np

path = 'bot/logs/session_20261117_165453.jsonl'
lines = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]

wins = sum(1 for l in lines if l['is_win'])
losses = len(lines) - wins
non_zero_spins = [l for l in lines if l['outcome'] != 'ZERO']
nz_wins = sum(1 for l in non_zero_spins if l['is_win'])
zeros = sum(1 for l in lines if l['outcome'] == 'ZERO')

print(f"Total spins: {len(lines)}")
print(f"Wins: {wins}, Losses: {losses}, Zeros: {zeros}")
print(f"Overall Win Rate: {wins/len(lines)*100:.2f}%")
print(f"Non-Zero Win Rate: {nz_wins/len(non_zero_spins)*100:.2f}% (z = {(nz_wins/len(non_zero_spins) - 0.5)/math.sqrt(0.25/len(non_zero_spins)):+.2f})")
print(f"Start Bank: {lines[0]['bankroll'] - lines[0]['net_profit']:,} ₽, End Bank: {lines[-1]['bankroll']:,} ₽")
print(f"Net Profit: {lines[-1]['bankroll'] - (lines[0]['bankroll'] - lines[0]['net_profit']):+,} ₽")

# Check steps distribution and high steps
max_bet = max(l['bet_amount'] for l in lines)
print(f"\nMax bet placed: {max_bet:,} ₽")

# Reconstruct actual step at placement:
# In bot logging, let's see how step was logged:
# Let's inspect all spins where bet_amount > 50000 or step > 3
print("\n--- High Bet / High Step Events (bet >= 50,000 ₽ or step >= 4) ---")
for idx, l in enumerate(lines):
    if l['bet_amount'] >= 50000 or l['step'] >= 4:
        # Show preceding 5 spins for context
        prec = [lines[j]['outcome'] for j in range(max(0, idx-5), idx)]
        print(f"Spin #{l['spin']} | Step: {l['step']} | Bet: {l['bet_amount']:,} ₽ on {l['bet_color']} | Outcome: {l['outcome']} | Win: {l['is_win']} | CDT: {l['cdt']:,} | Mode: {l['mode']} | Prev: {prec}")

# Analyze behavior on streak = 1 and streak = 2:
# What does the engine predict when streak = 1? Does it fade or follow? What is actual win rate?
# What does the engine predict when streak = 2? Does it fade or follow? What is actual win rate?
print("\n--- Behavior on Streak Transitions in this session ---")
streak_1_fades = 0
streak_1_fade_wins = 0
streak_1_follows = 0
streak_1_follow_wins = 0

streak_2_fades = 0
streak_2_fade_wins = 0
streak_2_follows = 0
streak_2_follow_wins = 0

streak_3_fades = 0
streak_3_fade_wins = 0
streak_3_follows = 0
streak_3_follow_wins = 0

hist_nz = []
for idx, l in enumerate(lines):
    out = l['outcome']
    pred = l['bet_color']
    if hist_nz:
        cur_col = hist_nz[-1]
        # Calculate current streak before this spin
        s = 1
        for k in range(len(hist_nz) - 2, -1, -1):
            if hist_nz[k] == cur_col: s += 1
            else: break
        
        is_fade = (pred != cur_col)
        is_follow = (pred == cur_col)
        actual_is_fade = (out != cur_col and out != 'ZERO')
        actual_is_follow = (out == cur_col)

        if s == 1:
            if is_fade:
                streak_1_fades += 1
                if actual_is_fade: streak_1_fade_wins += 1
            elif is_follow:
                streak_1_follows += 1
                if actual_is_follow: streak_1_follow_wins += 1
        elif s == 2:
            if is_fade:
                streak_2_fades += 1
                if actual_is_fade: streak_2_fade_wins += 1
            elif is_follow:
                streak_2_follows += 1
                if actual_is_follow: streak_2_follow_wins += 1
        elif s >= 3:
            if is_fade:
                streak_3_fades += 1
                if actual_is_fade: streak_3_fade_wins += 1
            elif is_follow:
                streak_3_follows += 1
                if actual_is_follow: streak_3_follow_wins += 1

    if out != 'ZERO':
        hist_nz.append(out)

print(f"When Streak == 1:")
print(f"  Fades (betting switch): {streak_1_fades} times, Won: {streak_1_fade_wins} ({streak_1_fade_wins/max(1,streak_1_fades)*100:.1f}%)")
print(f"  Follows (betting repeat): {streak_1_follows} times, Won: {streak_1_follow_wins} ({streak_1_follow_wins/max(1,streak_1_follows)*100:.1f}%)")

print(f"\nWhen Streak == 2:")
print(f"  Fades (betting break/pair break): {streak_2_fades} times, Won: {streak_2_fade_wins} ({streak_2_fade_wins/max(1,streak_2_fades)*100:.1f}%)")
print(f"  Follows (betting 3 in a row): {streak_2_follows} times, Won: {streak_2_follow_wins} ({streak_2_follow_wins/max(1,streak_2_follows)*100:.1f}%)")

print(f"\nWhen Streak >= 3:")
print(f"  Fades (betting bounce/fade): {streak_3_fades} times, Won: {streak_3_fade_wins} ({streak_3_fade_wins/max(1,streak_3_fades)*100:.1f}%)")
print(f"  Follows (betting streak continuation): {streak_3_follows} times, Won: {streak_3_follow_wins} ({streak_3_follow_wins/max(1,streak_3_follows)*100:.1f}%)")
