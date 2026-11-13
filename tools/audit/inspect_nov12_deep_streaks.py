import json

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    logs = json.load(f)["logs"]

# Find where step >= 6 occurred
for i, e in enumerate(logs):
    if e["current_step"] >= 6 or e["current_bet"] >= 200000:
        print(f"\n--- Deep event at spin {i+1} (step={e['current_step']}, bet={e['current_bet']:,}) ---")
        start = max(0, i - 8)
        end = min(len(logs), i + 3)
        for j in range(start, end):
            item = logs[j]
            marker = "===> " if j == i else "     "
            print(
                f"{marker}spin {j+1:3d}: step={item['current_step']:2d} mode={item.get('current_mode'):10s} "
                f"pred={item['recommended_action']:5s} out={item['input_result']:5s} win={str(item['is_win']):5s} "
                f"bet={item['current_bet']:7,d} bal={item['current_balance']:9,d} net={item['net_profit']:+8,d}"
            )
