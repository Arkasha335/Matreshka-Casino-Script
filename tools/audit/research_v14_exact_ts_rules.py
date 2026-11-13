import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_v14_deep_audit import load_all_29

sessions = load_all_29()


def predict_ts_v13_with_rule(hist):
    if not hist:
        return "RED", 50, "АНАЛИЗ"
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
            return ("BLACK" if L1 == "RED" else "RED"), 82, "ЭХО-ПАТТЕРН"
        if L1 == L2 == L3 and L4 != L1:
            return "BLACK" if L1 == "RED" else "RED", 78, "ВОЛНА (СЛОМ СЕРИИ)"
    if len(nz) < 2:
        return nz[-1] if nz else "RED", 50, "АНАЛИЗ"
    L1, L2 = nz[-1], nz[-2]
    c_max = ms_r if cac == "RED" else ms_b
    bounce_threshold = max(3, c_max)
    if cac and c_max > 0 and cas >= bounce_threshold:
        rec = "BLACK" if cac == "RED" else "RED"
        conf = 90
        state = "ОТСКОК ОТ ПОТОЛКА"
    elif L1 == L2:
        if L1 == alpha and c_max > 2:
            rec = L1
            conf = 75
            state = "АЛЬФА-ТРЕНД"
        elif L1 == omega:
            rec = "BLACK" if L1 == "RED" else "RED"
            conf = 30
            state = "ОМЕГА-ЛОВУШКА"
        else:
            rec = "BLACK" if L1 == "RED" else "RED"
            conf = 50
            state = "НЕЙТРАЛЬНО"
    else:
        zm = PrngDetectorMirror.get_zebra_momentum(hist)
        rec = L1 if zm["followL1"] else ("BLACK" if L1 == "RED" else "RED")
        conf = zm["confidence"]
        state = (
            "ЧЕРЕДОВАНИЕ (FOLLOW)"
            if zm["followL1"]
            else "ЧЕРЕДОВАНИЕ (BREAK)"
        )
    if L1 == alpha and L2 == omega:
        osb = 0
        for i in range(len(nz) - 2, -1, -1):
            if nz[i] == omega:
                osb += 1
            else:
                break
        if osb >= 2:
            rec = alpha
            conf = 85
            state = "ЗАРОЖДЕНИЕ АЛЬФЫ"
    return rec, conf, state


ts_rule_stats = {}
for fn, outs in sessions:
    hist = []
    for o in outs:
        if not hist:
            hist.append(o)
            continue
        rec, conf, state = predict_ts_v13_with_rule(hist)
        is_nz = o != "ZERO"
        is_w = is_nz and o == rec
        st = ts_rule_stats.setdefault(
            state, {"tot": 0, "nz": 0, "wins": 0, "zeros": 0}
        )
        st["tot"] += 1
        if is_nz:
            st["nz"] += 1
            if is_w:
                st["wins"] += 1
        else:
            st["zeros"] += 1
        hist.append(o)

print(
    "=== EXACT TS v13.0 RULE-BY-RULE AUDIT (All 29 Sessions, 2,711 Spins) ==="
)
print(
    f"{'Rule / State Name':30s} | {'Total':5s} | {'NZ':5s} | {'Wins':5s} | "
    f"{'Overall W%':10s} | {'Non-Zero W%':11s} | {'Zeros':5s}"
)
print("-" * 88)
t_tot = t_nz = t_w = 0
for r_name, s in sorted(ts_rule_stats.items(), key=lambda x: -x[1]["tot"]):
    tot = s["tot"]
    nz = s["nz"]
    w = s["wins"]
    z = s["zeros"]
    ow = w / tot * 100 if tot > 0 else 0
    nzw = w / nz * 100 if nz > 0 else 0
    t_tot += tot
    t_nz += nz
    t_w += w
    print(
        f"{r_name:30s} | {tot:5d} | {nz:5d} | {w:5d} | "
        f"{ow:9.2f}% | {nzw:10.2f}% | {z:5d}"
    )
print("-" * 88)
print(
    f"{'TOTAL / AVERAGE':30s} | {t_tot:5d} | {t_nz:5d} | {t_w:5d} | "
    f"{t_w/t_tot*100:9.2f}% | {t_w/t_nz*100:10.2f}%"
)
