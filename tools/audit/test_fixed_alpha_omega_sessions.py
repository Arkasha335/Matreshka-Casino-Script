import os
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import js_round
from parity_ts_vs_python import exact_bet_1m, calc_net_win
from research_v14_deep_audit import load_all_29
from test_flip_alpha_omega import predict_fixed_alpha_omega
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


def run_predictor_eval(seqs, pred_fn, cfg_fn, init_bank, profile_fast=True):
    wins = busts = 0
    profits, hrs, dds = [], [], []
    max_losses = []
    for outs in seqs:
        bank = init_bank
        peak = bank
        max_dd = 0
        step = 1
        cdt = 0
        prev_bet = None
        seq_start = "ZEBRA"
        seq_n = None
        zis = 0
        hist = []
        cur_l = 0
        max_l = 0
        busted = False
        for o in outs:
            if bank < 1000:
                busted = True
                break
            cycle_cap = bank + cdt
            z10 = sum(1 for x in hist[-10:] if x == "ZERO")
            zs = profile_fast and (z10 >= 2 or zis >= 2)
            locked = (
                (cdt > 0)
                and profile_fast
                and (not zs)
                and (cycle_cap >= 3_000_000)
                and (seq_start == "ZEBRA")
            )
            eff_mode = "ZEBRA" if locked else "ZEBRA"
            # mode detection
            if profile_fast:
                raw_m = "TRANSITION" if z10 >= 3 else "ZEBRA"
            b0, mode_n = cfg_fn(eff_mode, cycle_cap)
            eff_n = (
                min(10, max(seq_n, mode_n), mode_n)
                if (zs and step >= 2 and seq_n is not None)
                else (min(mode_n, seq_n) if (cdt > 0 and seq_n) else mode_n)
            )
            bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
            pred = pred_fn(hist)
            was_start = cdt == 0 or step == 1
            if o == "ZERO":
                net = -bet
                cdt += bet
                step += 1
                zis += 1
                cur_l += 1
            elif o == pred:
                net = calc_net_win(bet)
                cdt = max(0, cdt - net)
                if cdt == 0:
                    step = 1
                    zis = 0
                cur_l = 0
            else:
                net = -bet
                cdt += bet
                step += 1
                cur_l += 1
            max_l = max(max_l, cur_l)
            bank += net
            if bank > peak:
                peak = bank
            max_dd = max(max_dd, peak - bank)
            hist.append(o)
            if cdt == 0:
                seq_start = eff_mode
                seq_n = None
                zis = 0
            elif was_start:
                seq_start = eff_mode
                seq_n = cfg_fn(eff_mode, cycle_cap)[1]
            prev_bet = bet
        if bank < 1000:
            busted = True
        prof = bank - init_bank
        if prof > 0 and not busted:
            wins += 1
        if busted:
            busts += 1
        profits.append(prof)
        dds.append(max_dd)
        max_losses.append(max_l)
        hrs.append(prof * (270.0 / max(1, len(outs))))
    hrs.sort()
    return dict(
        win=wins / len(seqs) * 100,
        bust=busts / len(seqs) * 100,
        med=statistics.median(hrs),
        p90=hrs[int(0.9 * (len(hrs) - 1))],
        med_raw=statistics.median(profits),
        max_dd=max(dds),
        max_ls=max(max_losses),
        avg_max_ls=statistics.mean(max_losses),
    )


from parity_ts_vs_python import predict_v13

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

print(
    "=== FINANCIAL BENCHMARK: v13.0 vs v14 Alpha/Omega Corrected Predictor ==="
)
for name, p_fn in [
    ("v13.0 (Baseline)", lambda h: predict_v13(h, 15, 3)),
    ("v14.0 (Alpha/Omega Fixed)", predict_fixed_alpha_omega),
]:
    print(f"\n--- {name} ---")
    for prof_name, cfg, bk in [
        ("APEX", cfg_apex, 3_800_000),
        ("TURBO", cfg_turbo, 4_040_371),
    ]:
        re = run_predictor_eval(early, p_fn, cfg, bk, True)
        rl = run_predictor_eval(late, p_fn, cfg, bk, True)
        ra = run_predictor_eval(all29, p_fn, cfg, bk, True)
        r11 = run_predictor_eval(nov11_outs, p_fn, cfg, bk, True)
        r12 = run_predictor_eval(nov12_outs, p_fn, cfg, bk, True)
        print(
            f"  {prof_name} @ {bk/1e6:.1f}M | Early: {re['win']:5.1f}% | Late: {rl['win']:5.1f}% | "
            f"All29: {ra['win']:5.1f}% Med: {ra['med']:>+10,.0f}/h MaxDD: {ra['max_dd']:>9,d} (MaxLS={ra['max_ls']}) | "
            f"Nov11: Win={r11['win']:.0f}% Raw={r11['med_raw']:>+9,.0f} | Nov12: Win={r12['win']:.0f}% Raw={r12['med_raw']:>+9,.0f} MaxDD={r12['max_dd']:>8,d}"
        )
