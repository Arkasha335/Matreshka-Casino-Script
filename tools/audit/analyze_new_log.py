import json, os, sys, math

with open(r'd:/Downloads/matreshka_session_2026-11-08 (1).json', 'r', encoding='utf-8') as f:
    d = json.load(f)

logs = d.get('logs', [])
print(f"Log has {len(logs)} spins.")

# Let's inspect the actual bets made in that log:
spins_1_6 = logs[:6]
print("Spins 1-6:")
for i, l in enumerate(spins_1_6):
    print(f"Spin {i+1}: Step {l['current_step']}, Bet: {l['current_bet']:,}, Mode: {l['current_mode']}, Result: {l['input_result']}, Won: {l['is_win']}")
