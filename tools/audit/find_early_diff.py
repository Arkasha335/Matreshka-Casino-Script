import os
import sys

sys.path.append(os.path.dirname(__file__))
from parity_ts_vs_python import predict_v13
from research_v14_deep_audit import load_all_29
from research_v14_predictor_optimizer import pred_c2, run_sim, cfg_apex

sessions = load_all_29()
early_sessions = [
    (fn, outs)
    for fn, outs in sessions
    if not any(
        t in fn
        for t in [
            "2026-04-07",
            "2026-04-08",
            "2026-04-09",
            "2026-04-14",
            "2026-11",
        ]
    )
]

for fn, outs in early_sessions:
    wb, ddb = run_sim([outs], cfg_apex, 3_800_000)
    w2, dd2 = run_sim([outs], cfg_apex, 3_800_000)
    # Check baseline vs candidate 2
    # Baseline:
    bank_b = 3_800_000
    b_b = []
    # Candidate 2:
    bank_2 = 3_800_000
    # Let's see which one failed
    from research_v14_predictor_optimizer import evaluate_candidate

    # Let's inspect where the two predictors diverge on this session
    hist = []
    divs = 0
    for o in outs:
        pb = predict_v13(hist, 15, 3)
        p2 = pred_c2(hist)
        if pb != p2:
            divs += 1
        hist.append(o)
    print(f"{fn:35s} (len={len(outs):3d}): divs={divs:2d}")
