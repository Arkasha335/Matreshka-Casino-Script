import csv
from tools.audit.engine_mirror import PrngDetectorMirror

with open('bot/logs/session_20261119_223110.csv', 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

history = []
deep_chains = []
current_chain = []

for idx, r in enumerate(rows):
    rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(history)
    spin_info = {
        'spin': int(r['spin']),
        'step': int(r['step']),
        'bet': float(r['bet_amount']),
        'bet_color': r['bet_color'],
        'rec': rec,
        'conf': conf,
        'state': state,
        'outcome': r['outcome'],
        'num': int(r['winning_num']),
        'is_win': r['is_win'] == 'WIN',
        'cdt': float(r['cdt']),
        'bankroll': float(r['bankroll'])
    }
    
    if spin_info['step'] > 1:
        current_chain.append(spin_info)
    else:
        if current_chain and any(s['step'] >= 4 for s in current_chain):
            deep_chains.append(current_chain)
        current_chain = [spin_info]
        
    history.append({
        'outcome': r['outcome'],
        'betAmount': float(r['bet_amount']),
        'betColor': r['bet_color'],
        'isWin': r['is_win'] == 'WIN',
        'netProfit': float(r['net_profit'])
    })

if current_chain and any(s['step'] >= 4 for s in current_chain):
    deep_chains.append(current_chain)

print(f"Total deep chains (step >= 4): {len(deep_chains)}")
for i, chain in enumerate(deep_chains):
    max_s = max(s['step'] for s in chain)
    print(f"\n=== Deep Chain #{i+1} (Max Step: {max_s}) ===")
    for s in chain:
        w_str = 'WIN ' if s['is_win'] else 'LOSS'
        print(f"  Spin {s['spin']:3d} | Step {s['step']} | Bet: {s['bet']:7,.0f} on {s['bet_color']:5s} | Out: {s['outcome']:5s} ({s['num']:2d}) | {w_str} | Conf: {s['conf']}% | State: {s['state']}")
