import json

with open(r'd:\Downloads\matreshka_session_2026-11-08.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for i, x in enumerate(data['logs']):
    in_res = x['input_result']
    rec = x['recommended_action']
    win = str(x['is_win'])
    bet = x['current_bet']
    step = x['current_step']
    mode = x.get('current_mode', '')
    det = x.get('server_state_detected', '')
    print(f"{i+1:2d} | In: {in_res:5s} | Rec: {rec:5s} | Win: {win:5s} | Bet: {bet:7d} | Step: {step} | Mode: {mode:10s} | Detected: {det}")
