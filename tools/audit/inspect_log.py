import json

with open(r'd:/Downloads/matreshka_session_2026-11-08 (1).json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('Metadata:', data.get('metadata'))
logs = data.get('logs', [])
print(f'Total spins: {len(logs)}')
for i, l in enumerate(logs):
    print(f"{i+1:2d} | Step: {l.get('current_step')} | Bet: {l.get('current_bet'):8d} | Mode: {l.get('current_mode'):<10} | Rec: {l.get('recommended_action'):<5} | Res: {l.get('input_result'):<5} | Win: {l.get('is_win')} | Net: {l.get('net_profit'):+10.2f} | Bal: {l.get('current_balance'):10.2f}")
