import json

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    logs = json.load(f)["logs"]

for i in range(23, 29):
    e = logs[i]
    print(f"spin {i+1}: dt={e.get('time_since_last_spin')} step={e['current_step']} bet={e['current_bet']} state={e.get('server_state_detected')}")
