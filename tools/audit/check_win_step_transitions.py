import json

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    logs = json.load(f)["logs"]

for i in range(len(logs) - 1):
    curr = logs[i]
    nxt = logs[i + 1]
    if curr["is_win"] and nxt["current_step"] != 1:
        print(
            f"After WIN at spin {i+1} (step={curr['current_step']}): "
            f"next spin {i+2} has step={nxt['current_step']} bet={nxt['current_bet']}!"
        )
