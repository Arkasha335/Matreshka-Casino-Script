import json

with open(r'd:\Downloads\matreshka_session_2026-11-08.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for i, x in enumerate(data['logs']):
    print(f"#{i+1:2d} | Result: {x['input_result']:5s} | Rec: {x['recommended_action']:5s} | Step: {x['current_step']} | Bet: {x['current_bet']:7d} | Reason: {ascii(x.get('server_state_detected', ''))}")
