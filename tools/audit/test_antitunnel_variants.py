import os
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from parity_ts_vs_python import predict_v13
from research_v14_deep_audit import load_all_29

sessions = load_all_29()

# Let's test Trend Following on deep streaks:
# If cas >= 4 and cas > c_max_before_streak, what if we FOLLOW instead of REVERSE?
def predict_antitunnel(hist, window=15, min_cmax=3, max_reversal_streak=4):
    if not hist:
        return "RED"
    nz = [h for h in hist if h != "ZERO"]
    win_nz = nz[-window:]
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
    alpha = (
        "RED"
        if win_nz and rc / len(win_nz) > 0.55
        else ("BLACK" if win_nz and bc / len(win_nz) > 0.55 else "NEUTRAL")
    )
    omega = "BLACK" if alpha == "RED" else ("RED" if alpha == "BLACK" else "NEUTRAL")
    cac = nz[-1] if nz else None
    cas = 0
    for h in reversed(nz):
        if h == cac:
            cas += 1
        else:
            break
    if len(nz) >= 4:
        L1, L2, L3, L4 = nz[-1], nz[-2], nz[-3], nz[-4]
        if L1 == L3 and L2 == L4 and L1 != L2:
            return "BLACK" if L1 == "RED" else "RED"
        if L1 == L2 == L3 and L4 != L1:
            return "BLACK" if L1 == "RED" else "RED"
    if len(nz) < 2:
        return nz[-1] if nz else "RED"
    L1, L2 = nz[-1], nz[-2]
    c_max = ms_r if cac == "RED" else ms_b

    # ANTITUNNEL: If streak is very long (>= max_reversal_streak), DO NOT REVERSE, follow the trend!
    if cas >= max_reversal_streak:
        return cac  # Follow trend!

    bounce_threshold = max(min_cmax, c_max)
    if cac and c_max > 0 and cas >= bounce_threshold:
        rec = "BLACK" if cac == "RED" else "RED"
    elif L1 == L2:
        if L1 == alpha and c_max > 2:
            rec = L1
        else:
            rec = "BLACK" if L1 == "RED" else "RED"
    else:
        zm = PrngDetectorMirror.get_zebra_momentum(hist)
        rec = L1 if zm["followL1"] else ("BLACK" if L1 == "RED" else "RED")
    if L1 == alpha and L2 == omega:
        osb = 0
        for i in range(len(nz) - 2, -1, -1):
            if nz[i] == omega:
                osb += 1
            else:
                break
        if osb >= 2:
            rec = alpha
    return rec


print("=== TESTING PREDICTOR VARIANTS ACROSS ALL 29 SESSIONS (2,711 SPINS) ===")
for cap in [3, 4, 5, 6, 7, 99]:
    w_all = 0
    w_nz = 0
    tot_sp = 0
    tot_nz = 0
    max_losses = []
    for fn, outs in sessions:
        hist = []
        cur_loss = 0
        max_l = 0
        for o in outs:
            tot_sp += 1
            pred = (
                predict_v13(hist, 15, 3)
                if cap == 99
                else predict_antitunnel(hist, 15, 3, cap)
            )
            is_w = o == pred and o != "ZERO"
            if is_w:
                w_all += 1
                w_nz += 1
                cur_loss = 0
            else:
                cur_loss += 1
                max_l = max(max_l, cur_loss)
            if o != "ZERO":
                tot_nz += 1
            hist.append(o)
        max_losses.append(max_l)
    lbl = f"v13 (No cap)" if cap == 99 else f"Anti-Tunnel cas>={cap}"
    print(
        f"{lbl:22s}: Overall Win={w_all/tot_sp*100:5.2f}% | "
        f"Non-Zero Win={w_nz/tot_nz*100:5.2f}% | Max Loss Streak={max(max_losses):2d} "
        f"(Avg MaxLS={statistics.mean(max_losses):.1f})"
    )
