import json, os

targets = [
    r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json',
    r'D:\Vibe\matreshka-quantum\log storage\matreshka_session_2026-04-08.json',
    r'D:\Vibe\matreshka-quantum\log storage\matreshka_session_2026-04-05 (1).json',
    r'D:\Vibe\matreshka-quantum\log storage\matreshka_session_2026-04-07 (3).json',
]

for p in targets:
    with open(p, 'r', encoding='utf-8') as f: d = json.load(f)
    logs = d.get('logs', [])
    print(f"\n=== {os.path.basename(p)} (N={len(logs)}, meta={d.get('metadata')}) ===")
    for i, l in enumerate(logs, 1):
        b = l.get('current_bet', l.get('betAmount', 0))
        st = l.get('current_step', l.get('step', 0))
        m = l.get('current_mode', '?')
        bal = l.get('current_balance', l.get('balance', 0))
        res = l.get('input_result', l.get('outcome'))
        rec = l.get('recommended_action', l.get('betColor'))
        if b >= 30000 or i <= 5 or i >= len(logs) - 2:
            print(f"  Sp {i:3d} | {str(m):<10} | St={st:2d} | Rec={str(rec):<5} Out={str(res):<5} | Bet={b:>9,.0f} | Bal={bal:>10,.0f}")
