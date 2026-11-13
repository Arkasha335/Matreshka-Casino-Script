import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from parity_ts_vs_python import predict_v13
from research_v14_deep_audit import load_all_29

sessions = load_all_29()


def predict_fixed_alpha_omega(hist):
    if not hist:
        return "RED"
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
    bounce_threshold = max(3, c_max)
    if cac and c_max > 0 and cas >= bounce_threshold:
        rec = "BLACK" if cac == "RED" else "RED"
    elif L1 == L2:
        # HERE IS THE TEST:
        # What if when L1 == alpha we predict BREAK (opposite)?
        # And when L1 == omega we predict FOLLOW (L1)?
        if L1 == alpha and c_max > 2:
            rec = (
                "BLACK" if L1 == "RED" else "RED"
            )  # FLIPPED: break saturated alpha!
        elif L1 == omega:
            rec = L1  # FLIPPED: follow underdog regime shift!
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


# Test baseline v13 vs fixed alpha/omega
w_base = 0
w_fixed = 0
tot = 0
tot_nz = 0

for fn, outs in sessions:
    hist = []
    for o in outs:
        p_b = predict_v13(hist, 15, 3)
        p_f = predict_fixed_alpha_omega(hist)
        if o == p_b and o != "ZERO":
            w_base += 1
        if o == p_f and o != "ZERO":
            w_fixed += 1
        if o != "ZERO":
            tot_nz += 1
        tot += 1
        hist.append(o)

print("=== BASELINE v13 vs FLIPPED ALPHA/OMEGA (All 29 Sessions, 2,711 Spins) ===")
print(
    f"v13 Baseline:       Wins={w_base} / {tot_nz} ({w_base/tot_nz*100:.2f}% non-zero, {w_base/tot*100:.2f}% overall)"
)
print(
    f"Fixed Alpha/Omega:  Wins={w_fixed} / {tot_nz} ({w_fixed/tot_nz*100:.2f}% non-zero, {w_fixed/tot*100:.2f}% overall)"
)
print(f"Net Win Delta: {w_fixed - w_base:+d} wins across the dataset!")
