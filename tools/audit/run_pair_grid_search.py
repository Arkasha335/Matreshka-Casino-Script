import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_v14_deep_audit import load_all_29
from test_fixed_alpha_omega_sessions import run_predictor_eval, cfg_apex, cfg_turbo

sessions = load_all_29()
all29 = [o for _, o in sessions]
nov11 = [o for fn, o in sessions if "2026-11-11" in fn]
nov12 = [o for fn, o in sessions if "2026-11-12" in fn]


def test_config(alpha_rule, omega_rule, neutral_rule, sat_threshold=0.70):
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

        cac = nz[-1]
        cas = 0
        for h in reversed(nz):
            if h == cac:
                cas += 1
            else:
                break

        # 4-spin patterns
        if len(nz) >= 4:
            L1, L2, L3, L4 = nz[-1], nz[-2], nz[-3], nz[-4]
            if L1 == L3 and L2 == L4 and L1 != L2:
                return "BLACK" if L1 == "RED" else "RED"
            if L1 == L2 == L3 and L4 != L1:
                return "BLACK" if L1 == "RED" else "RED"

        L1, L2 = nz[-1], nz[-2]

        # Deep streak (cas >= 3) -> always fade opposite!
        if cas >= 3:
            return "BLACK" if cac == "RED" else "RED"

        # Pair (cas == 2)
        if L1 == L2:
            if L1 == alpha:
                if top_r >= sat_threshold:
                    return "BLACK" if L1 == "RED" else "RED"
                else:
                    return (
                        L1
                        if alpha_rule == "cont"
                        else ("BLACK" if L1 == "RED" else "RED")
                    )
            elif L1 == omega:
                return (
                    L1
                    if omega_rule == "cont"
                    else ("BLACK" if L1 == "RED" else "RED")
                )
            else:
                return (
                    L1
                    if neutral_rule == "cont"
                    else ("BLACK" if L1 == "RED" else "RED")
                )

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

    # Calculate metrics
    tot_spins = tot_nz = tot_wins = 0
    max_losses = []
    for fn, outs in sessions:
        hist = []
        cur_l = max_l = 0
        for o in outs:
            tot_spins += 1
            p = pred(hist)
            is_nz = o != "ZERO"
            if is_nz:
                tot_nz += 1
            if o == p and is_nz:
                tot_wins += 1
                cur_l = 0
            else:
                cur_l += 1
                max_l = max(max_l, cur_l)
            hist.append(o)
        max_losses.append(max_l)
    nz_wr = tot_wins / tot_nz * 100
    mls = max(max_losses)

    # Financials
    r_a = run_predictor_eval(all29, pred, cfg_apex, 3_800_000, False)
    r_t = run_predictor_eval(all29, pred, cfg_turbo, 4_040_371, False)
    r_11 = run_predictor_eval(nov11, pred, cfg_turbo, 4_040_371, False)
    r_12 = run_predictor_eval(nov12, pred, cfg_turbo, 4_040_371, False)

    return {
        "nz_wr": nz_wr,
        "mls": mls,
        "apex_win": r_a["win"],
        "apex_dd": r_a["max_dd"],
        "turbo_win": r_t["win"],
        "turbo_dd": r_t["max_dd"],
        "n11_win": r_11["win"],
        "n12_win": r_12["win"],
        "n12_raw": r_12["med_raw"],
    }


print("Testing variations...")
for a_r in ["break", "cont"]:
    for o_r in ["break", "cont"]:
        for n_r in ["break", "cont"]:
            for sat in [0.65, 0.70, 0.75]:
                res = test_config(a_r, o_r, n_r, sat)
                nz = res["nz_wr"]
                mls = res["mls"]
                aw = res["apex_win"]
                tw = res["turbo_win"]
                n11 = res["n11_win"]
                n12 = res["n12_win"]
                raw12 = res["n12_raw"]
                add = res["apex_dd"]
                tdd = res["turbo_dd"]
                print(
                    f"A={a_r:5s} O={o_r:5s} N={n_r:5s} Sat={sat:.2f} | NZ_WR={nz:5.2f}% MLS={mls:2d} | APEX={aw:5.1f}% DD={add:>9,d} | TURBO={tw:5.1f}% N11={n11:3.0f}% N12={n12:3.0f}% N12_Raw={raw12:>+10,.0f}"
                )
