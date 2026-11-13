import json
import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    logs = json.load(f)["logs"]

# Trace predictor internal logic for spins 104 to 111
hist = []
for i in range(103):
    hist.append(logs[i]["input_result"])

print("--- Inspecting predictor decisions on streak spins 104 to 110 ---")
for i in range(103, 110):
    item = logs[i]
    out = item["input_result"]
    nz = [h for h in hist if h != "ZERO"]
    win_nz = nz[-15:]
    rc = win_nz.count("RED")
    bc = len(win_nz) - rc
    ms_r = ms_b = cur = 0
    col = None
    for h in win_nz:
        cur = cur + 1 if h == col else 1
        col = h
        if col == "RED":
            ms_r = max(ms_r, cur)
        else:
            ms_b = max(ms_b, cur)
    cac = nz[-1] if nz else None
    cas = 0
    for h in reversed(nz):
        if h == cac:
            cas += 1
        else:
            break
    c_max = ms_r if cac == "RED" else ms_b

    pred_res = PrngDetectorMirror.get_recommendation_and_confidence(hist)

    print(
        f"Spin {i+1}: logged_pred={item['recommended_action']} actual_out={out} | "
        f"L1={nz[-1]} L2={nz[-2] if len(nz)>1 else None} L3={nz[-3] if len(nz)>2 else None} | "
        f"cas={cas} c_max={c_max} ms_r={ms_r} ms_b={ms_b} | "
        f"rule_applied='{pred_res[1]}' reason='{pred_res[2]}'"
    )
    hist.append(out)
