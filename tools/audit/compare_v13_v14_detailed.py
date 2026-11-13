import os
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from parity_ts_vs_python import exact_bet_1m, calc_net_win, predict_v13
from research_v14_deep_audit import load_all_29
from test_v14_antitunnel_bench import make_cfg

sessions = load_all_29()

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


def pred_v14(hist):
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
    omega = "BLACK" if alpha == "RED" else ("RED" if alpha == "BLACK" else "NEUTRAL")
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
        # Echo alternation A-B-A-B
        if L1 == L3 and L2 == L4 and L1 != L2:
            return "BLACK" if L1 == "RED" else "RED"
        # 3-Streak Break Wave (A-A-A after B)
        if L1 == L2 == L3 and L4 != L1:
            return "BLACK" if L1 == "RED" else "RED"

    L1, L2 = nz[-1], nz[-2]

    # Deep streak (cas >= 3) -> always fade opposite!
    if cas >= 3:
        return "BLACK" if cac == "RED" else "RED"

    # Pair (cas == 2)
    if L1 == L2:
        # Saturated Alpha mean reversion: break pair if dominance >= 70%
        if L1 == alpha and top_r >= 0.70:
            return "BLACK" if L1 == "RED" else "RED"
        # Moderate dominance / Underdog Omega / Neutral: continue pair
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


def run_single_session(outs, pred_fn, cfg_fn, init_bank=4_040_371):
    bank = init_bank
    peak = bank
    max_dd = 0
    step = 1
    cdt = 0
    prev_bet = None
    mode = "ZEBRA"
    seq_start = "ZEBRA"
    seq_n = None
    zis = 0
    hist = []
    busted = False
    wins = nz_wins = tot_spins = tot_nz = 0
    cur_ls = max_ls = 0

    for o in outs:
        if bank < 1000:
            busted = True
            break
        tot_spins += 1
        is_nz = o != "ZERO"
        if is_nz:
            tot_nz += 1
        cycle_cap = bank + cdt
        z10 = sum(1 for x in hist[-10:] if x == "ZERO")
        zs = z10 >= 2 or zis >= 2
        locked = (
            (cdt > 0) and (not zs) and (cycle_cap >= 3_000_000) and (seq_start == "ZEBRA")
        )
        eff_mode = "ZEBRA" if locked else mode
        b0, mode_n = cfg_fn(eff_mode, cycle_cap)
        if cdt > 0 and seq_n is not None:
            eff_n = (
                min(10, max(seq_n, mode_n), mode_n)
                if (zs and step >= 2)
                else min(mode_n, seq_n)
            )
        else:
            eff_n = mode_n
        bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
        pred = pred_fn(hist)
        was_start = cdt == 0 or step == 1

        if o == "ZERO":
            net = -bet
            cdt += bet
            step += 1
            zis += 1
            cur_ls += 1
        elif o == pred:
            net = calc_net_win(bet)
            cdt = max(0, cdt - net)
            wins += 1
            nz_wins += 1
            cur_ls = 0
            if cdt == 0:
                step = 1
                zis = 0
        else:
            net = -bet
            cdt += bet
            step += 1
            cur_ls += 1
        max_ls = max(max_ls, cur_ls)
        bank += net
        if bank > peak:
            peak = bank
        max_dd = max(max_dd, peak - bank)
        hist.append(o)

        raw_m = PrngDetectorMirror.detect_mode(hist)
        z10_n = sum(1 for x in hist[-10:] if x == "ZERO")
        mode = "TRANSITION" if (z10_n >= 3 and raw_m == "ZEBRA") else raw_m

        if cdt == 0:
            seq_start = mode
            seq_n = None
            zis = 0
        elif was_start:
            seq_start = eff_mode
            seq_n = cfg_fn(eff_mode, cycle_cap)[1]
        else:
            z10_next = sum(1 for x in hist[-10:] if x == "ZERO")
            if (z10_next >= 2 or zis >= 2) and step >= 2:
                nxt_n = cfg_fn(mode, bank + cdt)[1]
                seq_n = min(10, max(seq_n if seq_n is not None else nxt_n, nxt_n))
        prev_bet = bet

    prof = bank - init_bank
    return {
        "prof": prof,
        "busted": busted,
        "max_dd": max_dd,
        "max_ls": max_ls,
        "nz_wr": nz_wins / tot_nz * 100 if tot_nz else 0,
        "tot_spins": tot_spins,
    }


print("=== HEAD-TO-HEAD AUDIT: v13 vs v14 ON ALL 29 SESSIONS (TURBO 4.0M) ===")
print(
    f"{'Session Name':36s} | {'v13 Profit':>12s} {'v13 DD':>10s} {'MLS':>3s} {'NZ WR':>6s} | {'v14 Profit':>12s} {'v14 DD':>10s} {'MLS':>3s} {'NZ WR':>6s} | {'Delta':>12s}"
)
print("-" * 115)

tot_v13_prof = 0
tot_v14_prof = 0
v13_wins = 0
v14_wins = 0

for fn, outs in sessions:
    r13 = run_single_session(outs, lambda h: predict_v13(h, 15, 3), cfg_turbo)
    r14 = run_single_session(outs, pred_v14, cfg_turbo)
    tot_v13_prof += r13["prof"]
    tot_v14_prof += r14["prof"]
    if not r13["busted"] and r13["prof"] > 0:
        v13_wins += 1
    if not r14["busted"] and r14["prof"] > 0:
        v14_wins += 1
    delta = r14["prof"] - r13["prof"]
    p13_str = "BUST" if r13["busted"] else f"{r13['prof']:>+12,d}"
    p14_str = "BUST" if r14["busted"] else f"{r14['prof']:>+12,d}"
    print(
        f"{os.path.basename(fn):36s} | {p13_str} {r13['max_dd']:>10,d} {r13['max_ls']:3d} {r13['nz_wr']:5.1f}% | {p14_str} {r14['max_dd']:>10,d} {r14['max_ls']:3d} {r14['nz_wr']:5.1f}% | {delta:>+12,d}"
    )

print("-" * 115)
print(
    f"TOTALS | v13 Wins: {v13_wins}/29 ({v13_wins/29*100:.1f}%) Prof: {tot_v13_prof:>+14,d} | v14 Wins: {v14_wins}/29 ({v14_wins/29*100:.1f}%) Prof: {tot_v14_prof:>+14,d} | Delta: {tot_v14_prof - tot_v13_prof:>+14,d}"
)

print("\n=== HEAD-TO-HEAD AUDIT: v13 vs v14 ON ALL 29 SESSIONS (APEX 3.8M) ===")
print(
    f"{'Session Name':36s} | {'v13 Profit':>12s} {'v13 DD':>10s} | {'v14 Profit':>12s} {'v14 DD':>10s} | {'Delta':>12s}"
)
print("-" * 90)

a13_wins = 0
a14_wins = 0
tot_a13_prof = 0
tot_a14_prof = 0

for fn, outs in sessions:
    r13 = run_single_session(
        outs, lambda h: predict_v13(h, 15, 3), cfg_apex, 3_800_000
    )
    r14 = run_single_session(outs, pred_v14, cfg_apex, 3_800_000)
    tot_a13_prof += r13["prof"]
    tot_a14_prof += r14["prof"]
    if not r13["busted"] and r13["prof"] > 0:
        a13_wins += 1
    if not r14["busted"] and r14["prof"] > 0:
        a14_wins += 1
    delta = r14["prof"] - r13["prof"]
    p13_str = "BUST" if r13["busted"] else f"{r13['prof']:>+12,d}"
    p14_str = "BUST" if r14["busted"] else f"{r14['prof']:>+12,d}"
    print(
        f"{os.path.basename(fn):36s} | {p13_str} {r13['max_dd']:>10,d} | {p14_str} {r14['max_dd']:>10,d} | {delta:>+12,d}"
    )

print("-" * 90)
print(
    f"TOTALS APEX | v13 Wins: {a13_wins}/29 ({a13_wins/29*100:.1f}%) Prof: {tot_a13_prof:>+14,d} | v14 Wins: {a14_wins}/29 ({a14_wins/29*100:.1f}%) Prof: {tot_a14_prof:>+14,d} | Delta: {tot_a14_prof - tot_a13_prof:>+14,d}"
)

