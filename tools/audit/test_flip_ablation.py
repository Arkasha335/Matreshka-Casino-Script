import os
import sys

sys.path.append(os.path.dirname(__file__))
from research_v14_deep_audit import load_all_29
from test_fixed_alpha_omega_sessions import run_predictor_eval, cfg_apex, cfg_turbo

sessions = load_all_29()
all29 = [o for _, o in sessions]
nov12_outs = [o for fn, o in sessions if "2026-11-12" in fn]
nov11_outs = [o for fn, o in sessions if "2026-11-11" in fn]


def make_pred(flip_alpha=False, flip_omega=False):
    def fn(hist):
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
        omega = (
            "BLACK"
            if alpha == "RED"
            else ("RED" if alpha == "BLACK" else "NEUTRAL")
        )
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
            if L1 == alpha and c_max > 2:
                rec = ("BLACK" if L1 == "RED" else "RED") if flip_alpha else L1
            elif L1 == omega:
                rec = L1 if flip_omega else ("BLACK" if L1 == "RED" else "RED")
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

    return fn


from engine_mirror import PrngDetectorMirror

print("=== COMPARING FLIP COMBINATIONS ===")
for fa, fo in [(False, False), (True, False), (False, True), (True, True)]:
    p_fn = make_pred(fa, fo)
    ra = run_predictor_eval(all29, p_fn, cfg_turbo, 4_040_371, True)
    r12 = run_predictor_eval(nov12_outs, p_fn, cfg_turbo, 4_040_371, True)
    print(
        f"FlipAlpha={str(fa):5s} FlipOmega={str(fo):5s} | "
        f"All29 Win={ra['win']:5.1f}% MaxLS={ra['max_ls']:2d} MaxDD={ra['max_dd']:>9,d} | "
        f"Nov12 Win={r12['win']:5.1f}% Raw={r12['med_raw']:>+10,.0f} MaxDD={r12['max_dd']:>8,d} MaxLS={r12['max_ls']}"
    )
