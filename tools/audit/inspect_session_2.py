import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Vibe\matreshka-quantum\log storage\matreshka_session_2026-04-05 (2).json", "r", encoding="utf-8") as f:
    data = json.load(f)

logs = data.get("logs", [])
print(f"Session 2026-04-05 (2): {len(logs)} spins")
for i, l in enumerate(logs):
    print(f"Spin {i+1:2d} | Out: {l['input_result']:<5} | Rec: {l['recommended_action']:<5} | Bet: {l.get('current_bet', 0):>10,d} | Step: {l.get('current_step', 1)} | Bal: {l.get('current_balance', 0):>12,.0f}")
