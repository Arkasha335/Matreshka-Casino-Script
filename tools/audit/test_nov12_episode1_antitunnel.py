import json
import os
import sys

sys.path.append(os.path.dirname(__file__))
from test_antitunnel_variants import predict_antitunnel

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    logs = json.load(f)["logs"]

hist = []
for i in range(103):
    hist.append(logs[i]["input_result"])

print("--- Simulating Anti-Tunnel cas>=5 on Spins 104-110 ---")
for i in range(103, 110):
    item = logs[i]
    out = item["input_result"]
    pred = predict_antitunnel(hist, 15, 3, max_reversal_streak=5)
    is_w = pred == out
    print(
        f"Spin {i+1}: logged_pred={item['recommended_action']} "
        f"antitunnel_pred={pred} actual_out={out} -> WIN={is_w}"
    )
    hist.append(out)
