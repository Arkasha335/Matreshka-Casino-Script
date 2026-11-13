import json
import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    logs = json.load(f)["logs"]

hist = []
for i in range(161):
    hist.append(logs[i]["input_result"])

print("--- Inspecting predictor decisions on streak spins 162 to 167 ---")
for i in range(161, 167):
    item = logs[i]
    out = item["input_result"]
    nz = [h for h in hist if h != "ZERO"]
    cac = nz[-1] if nz else None
    cas = 0
    for h in reversed(nz):
        if h == cac:
            cas += 1
        else:
            break
    pred_res = PrngDetectorMirror.get_recommendation_and_confidence(hist)
    print(
        f"Spin {i+1}: logged_pred={item['recommended_action']} actual_out={out} | "
        f"cas={cas} rule='{pred_res[1]}' reason='{pred_res[2]}'"
    )
    hist.append(out)
