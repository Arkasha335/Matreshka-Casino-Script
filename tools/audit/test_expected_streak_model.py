import os
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_v14_deep_audit import load_all_29
from test_v14_fade_depths import evaluate_pred

sessions = load_all_29()


def make_expected_len_pred(
    alpha_sat_break=0.70, exp_threshold=1.6, min_fade=3
):
    def pred(hist):
        if not hist:
            return "RED"
        nz = [h for h in hist if h != "ZERO"]
        if len(nz) < 2:
            return nz[-1] if nz else "RED"
        win_nz = nz[-15:]
        rc = win_nz.count("RED")
        bc = len(win_nz) - rc
        tot = len(win_nz)
        r_r = rc / tot
        b_r = bc / tot
        alpha = (
            "RED"
            if r_r > 0.55
            else ("BLACK" if b_r > 0.55 else "NEUTRAL")
        )
        omega = (
            "BLACK"
            if alpha == "RED"
            else ("RED" if alpha == "BLACK" else "NEUTRAL")
        )
        top_r = max(r_r, b_r)

        # Calculate streak history in window
        streaks_r = []
        streaks_b = []
        cur = 0
        col = None
        for h in win_nz:
            if h == col:
                cur += 1
            else:
                if col == "RED":
                    streaks_r.append(cur)
                elif col == "BLACK":
                    streaks_b.append(cur)
                col = h
                cur = 1
        if col == "RED":
            streaks_r.append(cur)
        elif col == "BLACK":
            streaks_b.append(cur)

        avg_sr = statistics.mean(streaks_r) if streaks_r else 1.5
        avg_sb = statistics.mean(streaks_b) if streaks_b else 1.5

        cac = nz[-1]
        cas = 0
        for h in reversed(nz):
            if h == cac:
                cas += 1
            else:
                break

        c_exp = avg_sr if cac == "RED" else avg_sb

        # 4-spin echo patterns
        if len(nz) >= 4:
            L1, L2, L3, L4 = nz[-1], nz[-2], nz[-3], nz[-4]
            if L1 == L3 and L2 == L4 and L1 != L2:
                return "BLACK" if L1 == "RED" else "RED"
            if L1 == L2 == L3 and L4 != L1:
                return "BLACK" if L1 == "RED" else "RED"

        L1, L2 = nz[-1], nz[-2]

        # Streak Fading: if cas >= min_fade, always bet opposite ("до упора ставить против нее")
        if cas >= min_fade:
            return "BLACK" if cac == "RED" else "RED"

        # Pair (cas == 2)
        if L1 == L2:
            # 1. Extreme Alpha Saturation: mean reversion break
            if L1 == alpha and top_r >= alpha_sat_break:
                return "BLACK" if L1 == "RED" else "RED"
            # 2. Local Expected Streak Length: if expected streak is low (alternating regime), break!
            elif c_exp <= exp_threshold:
                return "BLACK" if L1 == "RED" else "RED"
            # 3. Otherwise (moderate trend or high expected length), continue pair
            else:
                return L1

        # Alternation (cas == 1)
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

    return pred


print("=== EVALUATING EXPECTED STREAK CALIBRATION ===")
for eth in [1.2, 1.4, 1.5, 1.6, 1.8, 2.0]:
    for sat in [0.65, 0.70, 0.75]:
        p = make_expected_len_pred(
            alpha_sat_break=sat, exp_threshold=eth, min_fade=3
        )
        res = evaluate_pred(p)
        nz = res["nz_wr"]
        mls = res["mls"]
        aw = res["apex_win"]
        tw = res["turbo_win"]
        n11 = res["n11_win"]
        n12 = res["n12_win"]
        raw12 = res["n12_raw"]
        add = res["apex_dd"]
        print(
            f"ExpThresh={eth:.1f} Sat={sat:.2f} | NZ_WR={nz:5.2f}% MLS={mls:2d} | APEX={aw:5.1f}% DD={add:>9,d} | TURBO={tw:5.1f}% N11={n11:3.0f}% N12={n12:3.0f}% Raw12={raw12:>+10,.0f}"
        )
