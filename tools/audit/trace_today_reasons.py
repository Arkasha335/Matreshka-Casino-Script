import json
from collections import defaultdict

with open(r'd:\Downloads\matreshka_session_2026-11-08.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

logs = data['logs']

print("Detailed log breakdown of the 26 spins:")
for i, x in enumerate(logs):
    spin_num = i + 1
    res = x['input_result']
    rec = x['recommended_action']
    win = x['is_win']
    bet = x['current_bet']
    step = x['current_step']
    det = x.get('server_state_detected', '')
    print(f"#{spin_num:2d} | Result: {res:5s} | Rec: {rec:5s} | Win: {str(win):5s} | Step: {step} | Bet: {bet:7d} | Reason: {det}")
