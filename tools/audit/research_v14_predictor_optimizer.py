import os
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from parity_ts_vs_python import exact_bet_1m, calc_net_win
from research_v14_deep_audit import load_all_29
from test_v14_antitunnel_bench import make_cfg

sessions = load_all_29()
all29 = [o for _, o in sessions]
early = [
    o
    for fn, o in sessions
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
late = [
    o
    for fn, o in sessions
    if any(
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
nov11_outs = [o for fn, o in sessions if "2026-11-11" in fn]
nov12_outs = [o for fn, o in sessions if "2026-11-12" in fn]

cfg_apex = make_cfg((5000, 8), (2500, 10), (1400, 10))
cfg_turbo = make_cfg(
    (8500, 7),
    (5000, 8),
    (2000, 9),
    3_000_000,
    (6500, 8),
    (4500, 8),
    (2500, 8),
)


def evaluate_candidate(pred_fn, name="Candidate"):
    # 1. Raw winrate & max losing streak
    tot_spins = 0
    tot_nz = 0
    tot_wins = 0
    max_losses_per_sess = []

    for fn, outs in sessions:
        hist = []
        cur_l = 0
        max_l = 0
        for o in outs:
            tot_spins += 1
            pred = pred_fn(hist)
            is_nz = o != "ZERO"
            if is_nz:
                tot_nz += 1
            if o == pred and is_nz:
                tot_wins += 1
                cur_l = 0
            else:
                cur_l += 1
                max_l = max(max_l, cur_l)
            hist.append(o)
        max_losses_per_sess.append(max_l)

    nz_wr = tot_wins / tot_nz * 100
    ov_wr = tot_wins / tot_spins * 100
    max_ls = max(max_losses_per_sess)
    avg_max_ls = statistics.mean(max_losses_per_sess)

    # 2. Financial simulation on APEX 3.8M & TURBO 4.0M
    def run_sim(seqs, cfg_fn, init_bk):
        wins = 0
        dds = []
        for outs in seqs:
            bank = init_bk
            peak = bank
            mdd = 0
            step = 1
            cdt = 0
            pb = None
            seq_s = "ZEBRA"
            seq_n = None
            zis = 0
            hist = []
            busted = False
            for o in outs:
                if bank < 1000:
                    busted = True
                    break
                cap = bank + cdt
                z10 = sum(1 for x in hist[-10:] if x == "ZERO")
                zs = z10 >= 2 or zis >= 2
                locked = (
                    (cdt > 0)
                    and (not zs)
                    and (cap >= 3_000_000)
                    and (seq_s == "ZEBRA")
                )
                raw_m = PrngDetectorMirror.detect_mode(hist)
                z10_next = sum(1 for x in hist[-10:] if x == "ZERO")
                fast_m = "TRANSITION" if (z10_next >= 3 and raw_m == "ZEBRA") else raw_m
                eff_m = "ZEBRA" if locked else fast_m
                b0, mn = cfg_fn(eff_m, cap)
                eff_n = (
                    min(10, max(seq_n, mn), mn)
                    if (zs and step >= 2 and seq_n)
                    else (min(mn, seq_n) if (cdt > 0 and seq_n) else mn)
                )
                bet = exact_bet_1m(cdt, step, b0, eff_n, bank, pb)
                pred = pred_fn(hist)
                ws = cdt == 0 or step == 1
                if o == "ZERO":
                    net = -bet
                    cdt += bet
                    step += 1
                    zis += 1
                elif o == pred:
                    net = calc_net_win(bet)
                    cdt = max(0, cdt - net)
                    if cdt == 0:
                        step = 1
                        zis = 0
                else:
                    net = -bet
                    cdt += bet
                    step += 1
                bank += net
                if bank > peak:
                    peak = bank
                mdd = max(mdd, peak - bank)
                hist.append(o)
                if cdt == 0:
                    seq_s = eff_m
                    seq_n = None
                    zis = 0
                elif ws:
                    seq_s = eff_m
                    seq_n = cfg_fn(eff_m, cap)[1]
                pb = bet
            if not busted and bank > init_bk:
                wins += 1
            dds.append(mdd)
        return wins / len(seqs) * 100, max(dds)

    a_e, _ = run_sim(early, cfg_apex, 3_800_000)
    a_l, _ = run_sim(late, cfg_apex, 3_800_000)
    a_all, a_dd = run_sim(all29, cfg_apex, 3_800_000)
    t_all, t_dd = run_sim(all29, cfg_turbo, 4_040_371)
    t_11, _ = run_sim(nov11_outs, cfg_turbo, 4_040_371)
    t_12, _ = run_sim(nov12_outs, cfg_turbo, 4_040_371)

    print(
        f"{name:32s} | WR: {nz_wr:5.2f}% ({ov_wr:5.2f}%) | MaxLS: {max_ls:2d} (avg {avg_max_ls:.1f}) | "
        f"APEX: E={a_e:5.1f}% L={a_l:5.1f}% All={a_all:5.1f}% DD={a_dd:>9,d} | "
        f"TURBO: All={t_all:5.1f}% N11={t_11:3.0f}% N12={t_12:3.0f}% DD={t_dd:>9,d}"
    )


# 1. v13 baseline
from parity_ts_vs_python import predict_v13

evaluate_candidate(lambda h: predict_v13(h, 15, 3), "1. v13 Baseline")

# 2. Candidate: Neutralize Alpha/Omega pairs (do not follow saturated alpha, follow zebra momentum on pairs!)
def pred_c2(hist):
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
    # User rule: ON STREAKS (cas >= bounce_threshold), ALWAYS FADE THE STREAK (bet opposite)!
    if cac and c_max > 0 and cas >= bounce_threshold:
        rec = "BLACK" if cac == "RED" else "RED"
    elif L1 == L2:
        # Instead of following saturated alpha, fade it!
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


evaluate_candidate(pred_c2, "2. Fade Alpha Pairs (Always Fade)")

# 3. Candidate 3: Echo 2-2 pattern detector (XXYY -> XXYYX)
# In Matreshka RP, when pairs alternate: RR-BB-RR -> next is BB!
def pred_c3(hist):
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
        # Echo alternation A-B-A-B
        if L1 == L3 and L2 == L4 and L1 != L2:
            return "BLACK" if L1 == "RED" else "RED"
        # 3-Streak Break Wave (A-A-A after B)
        if L1 == L2 and L2 == L3 and L4 != L1:
            return "BLACK" if L1 == "RED" else "RED"
        # NEW PATTERN: Pair Echo A-A-B-B (L1==L2 and L3==L4 and L1!=L3) -> Pair continuation or break?
        # If L1==L2 and L3==L4: we are at the end of the second pair.
        # If it's a 2-2 zebra (RR-BB-RR-BB), next is L1's opposite!
    if len(nz) < 2:
        return nz[-1] if nz else "RED"
    L1, L2 = nz[-1], nz[-2]
    c_max = ms_r if cac == "RED" else ms_b
    bounce_threshold = max(3, c_max)
    if cac and c_max > 0 and cas >= bounce_threshold:
        rec = "BLACK" if cac == "RED" else "RED"
    elif L1 == L2:
        # Check if preceded by pair of opposite color (A-A-B-B):
        if len(nz) >= 4 and nz[-3] == nz[-4] and nz[-3] != L1:
            # It's an established 2-2 pattern! The second pair is complete, break to opposite!
            rec = "BLACK" if L1 == "RED" else "RED"
        elif L1 == alpha and c_max > 2:
            # Saturated alpha pair: break it!
            rec = "BLACK" if L1 == "RED" else "RED"
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


evaluate_candidate(pred_c3, "3. Pair-Echo 2-2 + Alpha Fade")

# 4. Candidate 4: Fast Alternation Enhancer
# In ZEBRA, when altRate >= 0.75, strictly follow alternation (predict opposite of L1)
def pred_c4(hist):
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
        rec = "BLACK" if L1 == "RED" else "RED"
    else:
        # Check last 6 non-zero spins alternation
        sub = nz[-6:]
        alt = sum(1 for i in range(1, len(sub)) if sub[i] != sub[i - 1])
        alt_r = alt / (len(sub) - 1) if len(sub) > 1 else 0
        if alt_r >= 0.60:
            rec = "BLACK" if L1 == "RED" else "RED"  # Continue alternating!
        else:
            rec = L1
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


evaluate_candidate(pred_c4, "4. Fast Alt Enhancer (alt>=0.60)")
