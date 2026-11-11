import hashlib
import glob
import json
import math
import os
import random
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round

TABLE_LIMIT = 1_000_000


def load_28():
    paths = sorted(
        glob.glob(r"D:\Vibe\matreshka-quantum\log storage\*.json")
        + [r"D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json"]
        + glob.glob(r"D:\Downloads\matreshka*.json")
        + glob.glob(r"D:\Downloads\quantum*.json")
    )
    skip = {
        "matreshka_session_2026-03-31.json",
        "matreshka_session_2026-04-01 (3).json",
        "matreshka_session_2026-03-31 (1).json",
        "matreshka_session_2026-03-31 (2).json",
        "matreshka_session_2026-03-31 (3).json",
    }
    res, seen = [], set()
    for p in paths:
        if not os.path.exists(p):
            continue
        fn = os.path.basename(p)
        if fn in skip:
            continue
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        logs = d.get("logs", []) if isinstance(d, dict) else d
        if fn == "matreshka_quantum_v11_2026-11-08.json":
            logs = logs[:22]
        outs = [e.get("input_result") or e.get("actual_outcome") or e.get("outcome") for e in logs]
        outs = [x for x in outs if x in ("RED", "BLACK", "ZERO")]
        h = hashlib.md5(",".join(outs).encode()).hexdigest()
        if outs and h not in seen:
            seen.add(h)
            res.append((fn, outs))
    return res


def gen_mc(n_sess, n_spins, p_zero, seed):
    rng = random.Random(seed)
    p_col = (1.0 - p_zero) * 0.5
    return [
        [
            "ZERO" if (u := rng.random()) < p_zero else ("RED" if u < p_zero + p_col else "BLACK")
            for _ in range(n_spins)
        ]
        for _ in range(n_sess)
    ]


def predict_param(hist, window=15, min_cmax=3):
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
    if cac and c_max > 0 and cas >= max(min_cmax, c_max):
        rec = "BLACK" if cac == "RED" else "RED"
    elif L1 == L2:
        rec = L1 if (L1 == alpha and c_max > 2) else ("BLACK" if L1 == "RED" else "RED")
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


def precompute_causal(outcome_lists, window=15, min_cmax=3):
    traces = []
    for outs in outcome_lists:
        hist = []
        curr_m = prev_m = "ZEBRA"
        fast_m = "ZEBRA"
        sde = 999
        sim = 0
        z10_bef = 0
        row = []
        for o in outs:
            rec = predict_param(hist, window=window, min_cmax=min_cmax)
            is_w = (o == rec and o != "ZERO")
            hm_bef, fm_bef, z_bef = curr_m, fast_m, z10_bef
            hist.append(o)
            z10_aft = sum(1 for x in hist[-10:] if x == "ZERO")
            raw_aft = PrngDetectorMirror.detect_mode(hist)
            fast_aft = "TRANSITION" if (z10_aft >= 3 and raw_aft == "ZEBRA") else raw_aft
            hm_aft, prev_m, sde, sim = PrngDetectorMirror.detect_mode_with_hysteresis(
                hist, prev_m, curr_m, sde, sim
            )
            curr_m, fast_m, z10_bef = hm_aft, fast_aft, z10_aft
            row.append((is_w, o == "ZERO", hm_bef, fm_bef, z_bef, hm_aft, fast_aft, z10_aft))
        traces.append(row)
    return traces


def calc_net_win(bet):
    return ((int(bet) * 98) + 50) // 100


def geom_sum_factor(n, x=2.025):
    return (math.pow(x, n) - 1.0) / (x - 1.0)


def exact_bet_1m(cdt, step, base_bet, target_steps, bankroll, prev_bet):
    int_w = int(math.floor(bankroll))
    if int_w <= 0:
        return 0
    if int_w < 1000:
        return int_w
    base_bet = max(1000, min(int(base_bet), int_w, TABLE_LIMIT))
    if cdt <= 0 or step <= 1:
        return base_bet
    rem = max(1, target_steps - step + 1)
    min_tbb = math.ceil(((cdt + base_bet) * 100) / 98.0)
    while calc_net_win(min_tbb) < cdt + base_bet:
        min_tbb += 1
    pb = int(prev_bet) if (prev_bet is not None and prev_bet > 0) else base_bet
    if rem == 1:
        cap = min(TABLE_LIMIT, int_w)
        bet = min(min_tbb, cap) if cdt < cap * 0.30 else cap
        return max(1000, min(cap, int(math.floor(bet))))
    x_table = math.pow(TABLE_LIMIT / max(1, pb), 1.0 / rem)
    hi = min(3.20, x_table)

    def gsum(x):
        s = 0.0
        b = float(pb)
        for _ in range(rem):
            b *= x
            s += b
        return s

    if hi < 2.025:
        if gsum(2.025) <= int_w:
            opt_x = 2.025
        else:
            lo, hfb = 1.01, 2.025
            if gsum(lo) > int_w:
                opt_x = lo
            else:
                for _ in range(25):
                    mid = 0.5 * (lo + hfb)
                    if gsum(mid) <= int_w:
                        lo = mid
                    else:
                        hfb = mid
                opt_x = lo
    elif gsum(hi) <= int_w:
        opt_x = hi
    elif gsum(2.025) > int_w:
        lo, hw = 1.01, 2.025
        if gsum(lo) > int_w:
            opt_x = lo
        else:
            for _ in range(25):
                mid = 0.5 * (lo + hw)
                if gsum(mid) <= int_w:
                    lo = mid
                else:
                    hw = mid
            opt_x = lo
    else:
        lo = 2.025
        for _ in range(25):
            mid = 0.5 * (lo + hi)
            if gsum(mid) <= int_w:
                lo = mid
            else:
                hi = mid
        opt_x = lo

    bet = max(min_tbb, js_round(pb * opt_x))
    if rem == 2:
        max_safe = min(
            calc_net_win(TABLE_LIMIT) - cdt - 100,
            math.floor((0.98 * int_w - cdt - 100) / 1.98),
        )
        min_be = math.ceil(((cdt + 100) * 100) / 98.0)
        while calc_net_win(min_be) < cdt + 100:
            min_be += 1
        if max_safe >= min_be:
            bet = min(bet, max_safe)
    return max(1000, min(int(math.floor(bet)), TABLE_LIMIT, int_w))


def cfg_for(profile, mode, cap):
    cap = max(10_000, cap)
    scale = max(0.15, min(TABLE_LIMIT, cap / 1.92) / 1_000_000.0)
    if profile == "SHIELD_CONSERVATIVE":
        b0, n = {"ZEBRA": (1700, 10), "TRANSITION": (1200, 10), "DANGER": (1000, 10)}[mode]
    elif profile == "TURBO_HARVEST":
        if cap >= 3_000_000:
            b0, n = {"ZEBRA": (8500, 7), "TRANSITION": (5000, 8), "DANGER": (2000, 9)}[mode]
        else:
            b0, n = {"ZEBRA": (6500, 8), "TRANSITION": (4500, 8), "DANGER": (2500, 8)}[mode]
    else:
        b0, n = {"ZEBRA": (5000, 8), "TRANSITION": (2500, 10), "DANGER": (1400, 10)}[mode]
    while n > 5 and 1000 * geom_sum_factor(n) > cap:
        n -= 1
    max_b0 = max(1000, int(math.floor(cap / geom_sum_factor(n) / 100.0) * 100))
    return max(1000, min(TABLE_LIMIT, max_b0, int(js_round(b0 * scale / 100.0) * 100))), n


def cfg_turbo_v125(mode, cap):
    cap = max(10_000, cap)
    scale = max(0.15, min(TABLE_LIMIT, cap / 1.92) / 1_000_000.0)
    if cap >= 3_000_000:
        b0, n = {"ZEBRA": (9000, 7), "TRANSITION": (5500, 8), "DANGER": (3000, 8)}[mode]
    else:
        b0, n = {"ZEBRA": (6500, 8), "TRANSITION": (4500, 8), "DANGER": (2500, 8)}[mode]
    while n > 5 and 1000 * geom_sum_factor(n) > cap:
        n -= 1
    max_b0 = max(1000, int(math.floor(cap / geom_sum_factor(n) / 100.0) * 100))
    return max(1000, min(TABLE_LIMIT, max_b0, int(js_round(b0 * scale / 100.0) * 100))), n


def eval_traces(traces, profile, init_bank, zero_shock=True, use_v125_turbo=False):
    is_fast = profile != "SHIELD_CONSERVATIVE"
    cfg_fn = (lambda m, c: cfg_turbo_v125(m, c)) if (use_v125_turbo and profile == "TURBO_HARVEST") else (lambda m, c: cfg_for(profile, m, c))
    wins = busts = 0
    profits, hrs, dds, end_banks = [], [], [], []
    for seq in traces:
        bank = init_bank
        peak = bank
        max_dd = 0
        step = 1
        cdt = 0
        prev_bet = None
        seq_start = "ZEBRA"
        seq_n = None
        zis = 0
        busted = False
        for is_w, is_z, hm_bef, fm_bef, z10_bef, hm_aft, fm_aft, z10_aft in seq:
            if bank < 1000:
                busted = True
                break
            cycle_cap = bank + cdt
            mode_bef = fm_bef if is_fast else hm_bef
            mode_aft = fm_aft if is_fast else hm_aft
            zs = zero_shock and is_fast and (z10_bef >= 2 or zis >= 2)
            locked = (cdt > 0) and is_fast and (not zs) and cycle_cap >= 3_000_000 and seq_start == "ZEBRA"
            eff_mode = "ZEBRA" if locked else mode_bef
            b0, mode_n = cfg_fn(eff_mode, cycle_cap)
            if cdt > 0 and seq_n is not None:
                eff_n = min(10, max(seq_n, mode_n), mode_n) if (zs and step >= 2) else min(mode_n, seq_n)
            else:
                eff_n = mode_n
            bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
            was_start = (cdt == 0 or step == 1)
            if is_w:
                net = calc_net_win(bet)
                cdt = max(0, cdt - net)
                if cdt == 0:
                    step = 1
                    zis = 0
            else:
                net = -bet
                cdt += bet
                step += 1
                if is_z:
                    zis += 1
            bank += net
            if bank > peak:
                peak = bank
            max_dd = max(max_dd, peak - bank)
            if cdt == 0:
                seq_start = mode_aft
                seq_n = None
                zis = 0
            elif was_start:
                seq_start = eff_mode
                seq_n = cfg_fn(eff_mode, cycle_cap)[1]
            else:
                if zero_shock and is_fast and (z10_aft >= 2 or zis >= 2) and step >= 2:
                    nxt_n = cfg_fn(mode_aft, bank + cdt)[1]
                    seq_n = min(10, max(seq_n if seq_n is not None else nxt_n, nxt_n))
            prev_bet = bet
        if bank < 1000:
            busted = True
        prof = bank - init_bank
        if prof > 0 and not busted:
            wins += 1
        if busted:
            busts += 1
        end_banks.append(bank)
        profits.append(prof)
        dds.append(max_dd)
        hrs.append(prof * (270.0 / max(1, len(seq))))
    hrs.sort()
    return dict(
        win=wins / len(traces) * 100,
        bust=busts / len(traces) * 100,
        med=statistics.median(hrs),
        p90=hrs[int(0.9 * (len(hrs) - 1))],
        med_raw=statistics.median(profits),
        max_dd=max(dds),
        end_banks=end_banks,
    )


if __name__ == "__main__":
    real_28 = load_28()
    early_i = [i for i, (fn, _) in enumerate(real_28) if not any(t in fn for t in ["2026-04-07", "2026-04-08", "2026-04-09", "2026-04-14", "2026-11"])]
    late_i = [i for i, (fn, _) in enumerate(real_28) if i not in early_i]
    nov11_i = [i for i, (fn, _) in enumerate(real_28) if fn == "matreshka_session_2026-11-11.json"]

    tr125_28 = precompute_causal([o for _, o in real_28], 20, 1)
    tr13_28 = precompute_causal([o for _, o in real_28], 15, 3)

    # Verify exact match against parity TS results if present
    ts_p = r"C:\Users\user\.gemini\antigravity\brain\8cb8961f-b2d1-43d1-b097-d60fa78963d3\scratch\ts_parity_build\ts_results.json"
    if os.path.exists(ts_p):
        ts_res = {r["key"]: r["bank"] for r in json.load(open(ts_p, "r", encoding="utf-8"))}
        mm = 0
        for prof in ["SHIELD_CONSERVATIVE", "APEX_IDEAL", "TURBO_HARVEST"]:
            for bk in [1_000_000, 2_000_000, 3_800_000, 6_500_000]:
                res = eval_traces(tr13_28, prof, bk, zero_shock=(prof != "SHIELD_CONSERVATIVE"))
                for (fn, _), eb in zip(real_28, res["end_banks"]):
                    if ts_res[f"{prof}|{bk}|{fn}"] != eb:
                        mm += 1
        print(f"STRICT CAUSAL VS COMPILED TS CROSS-CHECK: runs=336, mismatches={mm}")
        if mm > 0:
            sys.exit(1)

    tr125_m1_4 = precompute_causal(gen_mc(2000, 100, 0.04, 2026), 20, 1)
    tr125_m2_4 = precompute_causal(gen_mc(2000, 270, 0.04, 7777), 20, 1)
    tr125_m2_5 = precompute_causal(gen_mc(2000, 270, 0.0502, 9999), 20, 1)

    tr13_m1_4 = precompute_causal(gen_mc(2000, 100, 0.04, 2026), 15, 3)
    tr13_m2_4 = precompute_causal(gen_mc(2000, 270, 0.04, 7777), 15, 3)
    tr13_m2_5 = precompute_causal(gen_mc(2000, 270, 0.0502, 9999), 15, 3)

    specs = [
        ("SHIELD v12.5.1 (causal)", "SHIELD_CONSERVATIVE", tr125_28, tr125_m1_4, tr125_m2_4, tr125_m2_5, False, False),
        ("SHIELD v13.0   (causal)", "SHIELD_CONSERVATIVE", tr13_28,  tr13_m1_4,  tr13_m2_4,  tr13_m2_5,  False, False),
        ("APEX   v12.5.1 (causal)", "APEX_IDEAL",          tr125_28, tr125_m1_4, tr125_m2_4, tr125_m2_5, False, False),
        ("APEX   v13.0   (causal)", "APEX_IDEAL",          tr13_28,  tr13_m1_4,  tr13_m2_4,  tr13_m2_5,  True,  False),
        ("TURBO  v12.5.1 (causal)", "TURBO_HARVEST",       tr125_28, tr125_m1_4, tr125_m2_4, tr125_m2_5, False, True),
        ("TURBO  v13.0   (causal)", "TURBO_HARVEST",       tr13_28,  tr13_m1_4,  tr13_m2_4,  tr13_m2_5,  True,  False),
    ]
    for title, prof, t28, tm1, tm4, tm5, zs, old_t in specs:
        print(f"\n=== {title} ===")
        te = [t28[i] for i in early_i]
        tl = [t28[i] for i in late_i]
        tn = [t28[i] for i in nov11_i]
        for bk in [1_000_000, 2_000_000, 3_800_000, 6_500_000]:
            re = eval_traces(te, prof, bk, zs, old_t)
            rl = eval_traces(tl, prof, bk, zs, old_t)
            ra = eval_traces(t28, prof, bk, zs, old_t)
            m1 = eval_traces(tm1, prof, bk, zs, old_t)
            m4 = eval_traces(tm4, prof, bk, zs, old_t)
            m5 = eval_traces(tm5, prof, bk, zs, old_t)
            print(
                f"  {bk/1e6:3.1f}M | E:{re['win']:>5.1f}% L:{rl['win']:>5.1f}% All28:{ra['win']:>5.1f}% Med {ra['med']:>+9,.0f}/h P90 {ra['p90']:>+10,.0f} | "
                f"MC100:{m1['win']:>5.1f}% | 1h4%:{m4['win']:>5.1f}% {m4['med']:>+9,.0f} (B {m4['bust']:>4.1f}%) | "
                f"1h5%:{m5['win']:>5.1f}% {m5['med']:>+9,.0f} (B {m5['bust']:>4.1f}%)"
            )
        rn = eval_traces(tn, prof, 3_668_458, zs, old_t)
        print(f"  Nov11 @3.67M | Win={rn['win']:.0f}% | Rate={rn['med']:>+10,.0f}/h | Raw={rn['med_raw']:>+9,.0f} | MaxDD={rn['max_dd']:>9,d}")
