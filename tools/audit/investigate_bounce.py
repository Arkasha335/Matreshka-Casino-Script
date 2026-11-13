import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_v14_deep_audit import load_all_29

sessions = load_all_29()

bounce_by_cas = {}

for fn, outs in sessions:
    hist = []
    for o in outs:
        if not hist:
            hist.append(o)
            continue
        nz = [h for h in hist if h != "ZERO"]
        cac = nz[-1] if nz else None
        cas = 0
        for h in reversed(nz):
            if h == cac:
                cas += 1
            else:
                break
        res = PrngDetectorMirror.get_recommendation_and_confidence(hist)
        if res[2] == "ОТСКОК ОТ ПОТОЛКА":
            st = bounce_by_cas.setdefault(
                cas, {"tot": 0, "nz": 0, "wins": 0, "losses": 0, "zeros": 0}
            )
            st["tot"] += 1
            if o != "ZERO":
                st["nz"] += 1
                if o == res[0]:
                    st["wins"] += 1
                else:
                    st["losses"] += 1
            else:
                st["zeros"] += 1
        hist.append(o)

print("=== ОТСКОК ОТ ПОТОЛКА BREAKDOWN BY CURRENT STREAK LENGTH (cas) ===")
print("cas (streak) | Total | NZ  | Wins | Overall W% | Non-Zero W% | Zeros")
print("-" * 65)
for cas, s in sorted(bounce_by_cas.items()):
    tot = s["tot"]
    nz = s["nz"]
    w = s["wins"]
    z = s["zeros"]
    ow = w / tot * 100 if tot > 0 else 0
    nzw = w / nz * 100 if nz > 0 else 0
    print(
        f"    cas = {cas:2d} | {tot:4d}  | {nz:3d} | {w:4d} |   {ow:5.2f}%   |   {nzw:5.2f}%    | {z:3d}"
    )
