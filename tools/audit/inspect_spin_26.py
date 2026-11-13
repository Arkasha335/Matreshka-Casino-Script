import json

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    logs = json.load(f)["logs"]

for i in range(18, 28):
    e = logs[i]
    print(
        f"spin {i+1:2d}: step={e['current_step']:2d} mode={e.get('current_mode'):10s} "
        f"bet={e['current_bet']:6d} win={str(e['is_win']):5s} bal={e['current_balance']} net={e['net_profit']:+7d}"
    )
