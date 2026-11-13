import json, glob, os, hashlib, statistics
from test_cas2_deep_study import load_clean, make_predictor
from parity_ts_vs_python import exact_bet_1m, calc_net_win
from test_v14_antitunnel_bench import make_cfg
from engine_mirror import PrngDetectorMirror

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
    s_max_step = 1

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
                min(10, max(seq_n, mode_n))
                if (zs and step >= 2)
                else min(mode_n, seq_n)
            )
        else:
            eff_n = mode_n

        bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
        if bet is None:
            busted = True
            break
        if step > s_max_step:
            s_max_step = step

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
        "max_step": s_max_step,
        "nz_wr": nz_wins / tot_nz * 100 if tot_nz else 0,
        "tot_spins": tot_spins,
    }

def run_suite(sessions, pred_fn, cfg_fn, init_bank):
    profs = []
    dds = []
    steps = []
    busted = 0
    sess_map = {}
    for name, outs in sessions:
        r = run_single_session(outs, pred_fn, cfg_fn, init_bank)
        profs.append(r["prof"])
        dds.append(r["max_dd"])
        steps.append(r["max_step"])
        if r["busted"]:
            busted += 1
        sess_map[name] = r
    return {
        "total_profit": sum(profs),
        "win_rate": sum(1 for p in profs if p > 0) / len(profs),
        "max_step": max(steps),
        "avg_max_step": sum(steps) / len(steps),
        "max_dd": max(dds),
        "busted": busted,
        "sess_map": sess_map,
    }

if __name__ == '__main__':
    sessions = load_clean()
    print(f'=== FINANCIAL BENCHMARK ACROSS ALL {len(sessions)} CLEAN SESSIONS ===\n')

    variants = [
        ('v14.0 Base (Pair Cont unless Alpha Sat >= 70%)', 'v14', 15),
        ('v15-C1 (Always Fade Pair: cas>=2 -> opposite)', 'always_fade', 15),
        ('v15-C2 (Fade unless Alpha Mom 60-70% & E[L]>=2.0)', 'fade_unless_alpha_momentum', 15),
        ('v15-C3 (Exp Streak Fade: E[L] <= 2.0)', 'exp_streak_fade', 15),
        ('v15-C4 (Fade in Zebra Momentum)', 'fade_in_zebra', 15),
        ('v15-C5 (Saturation Threshold 65%)', 'continue_unless_saturated', 15),
    ]

    for p_name, cfg, init_bank in [('TURBO_HARVEST', cfg_turbo, 4_000_000), ('APEX_IDEAL', cfg_apex, 3_800_000)]:
        print(f'--- PROFILE: {p_name} (Initial Bank: {init_bank:,} ₽) ---')
        for label, mode, w in variants:
            p_fn = make_predictor(mode, w)
            res = run_suite(sessions, p_fn, cfg, init_bank)
            
            n13 = next((v for k, v in res['sess_map'].items() if '2026-11-13' in k), None)
            n12 = next((v for k, v in res['sess_map'].items() if '2026-11-12' in k), None)
            n11 = next((v for k, v in res['sess_map'].items() if '2026-11-11' in k), None)
            
            n13_s = f"Nov13: +{n13['prof']:,} (st{n13['max_step']})" if n13 and n13['prof'] > 0 else f"Nov13: {n13['prof']:,}" if n13 else "Nov13: N/A"
            n12_s = f"Nov12: +{n12['prof']:,} (st{n12['max_step']})" if n12 and n12['prof'] > 0 else f"Nov12: {n12['prof']:,}" if n12 else "Nov12: N/A"
            n11_s = f"Nov11: +{n11['prof']:,} (st{n11['max_step']})" if n11 and n11['prof'] > 0 else f"Nov11: {n11['prof']:,}" if n11 else "Nov11: N/A"

            print(f"{label:<50} | Net: {res['total_profit']:>10,d} ₽ | WinSess: {res['win_rate']:.1%} | MaxSt: {res['max_step']} (avg {res['avg_max_step']:.1f}) | Busts: {res['busted']} | MaxDD: {res['max_dd']:>10,d} ₽ | {n13_s} | {n12_s}")
        print()
