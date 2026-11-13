import json
import math
import os
import random
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round
from parity_ts_vs_python import exact_bet_1m, calc_net_win
from research_v14_deep_audit import load_all_29
from test_antitunnel_variants import predict_antitunnel

sessions = load_all_29()

def run_causal_v14(seqs, cfg_fn, init_bank, profile_fast=True, zl_thresh=3_000_000, zero_shock=True, max_rev=5):
    wins = busts = 0
    profits, dds, hrs = [], [], []
    for outs in seqs:
        bank = init_bank; peak = bank; max_dd = 0
        step = 1; cdt = 0; prev_bet = None
        mode = 'ZEBRA'; prev_mode = 'ZEBRA'; sde = 999; sim = 0
        seq_start = 'ZEBRA'; seq_n = None; zis = 0; hist = []
        busted = False
        for o in outs:
            if bank < 1000: busted = True; break
            cycle_cap = bank + cdt
            z10 = sum(1 for x in hist[-10:] if x == 'ZERO')
            zs = zero_shock and profile_fast and (z10 >= 2 or zis >= 2)
            locked = (cdt > 0) and profile_fast and (not zs) and (zl_thresh is not None and cycle_cap >= zl_thresh) and (seq_start == 'ZEBRA')
            eff_mode = 'ZEBRA' if locked else mode
            b0, mode_n = cfg_fn(eff_mode, cycle_cap)
            if cdt > 0 and seq_n is not None:
                eff_n = min(10, max(seq_n, mode_n), mode_n) if (zs and step >= 2) else min(mode_n, seq_n)
            else:
                eff_n = mode_n
            bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
            pred = predict_antitunnel(hist, window=15, min_cmax=3, max_reversal_streak=max_rev)
            was_start = (cdt == 0 or step == 1)
            if o == 'ZERO':
                net = -bet; cdt += bet; step += 1; zis += 1
            elif o == pred:
                net = calc_net_win(bet); cdt = max(0, cdt - net)
                if cdt == 0: step = 1; zis = 0
            else:
                net = -bet; cdt += bet; step += 1
            bank += net
            if bank > peak: peak = bank
            max_dd = max(max_dd, peak - bank)
            hist.append(o)
            if profile_fast:
                raw_m = PrngDetectorMirror.detect_mode(hist)
                z10_n = sum(1 for x in hist[-10:] if x == 'ZERO')
                nm = 'TRANSITION' if (z10_n >= 3 and raw_m == 'ZEBRA') else raw_m
                prev_mode = mode if nm != mode else prev_mode
                sim = 1 if nm != mode else sim + 1
                mode = nm
            else:
                mode, prev_mode, sde, sim = PrngDetectorMirror.detect_mode_with_hysteresis(hist, prev_mode, mode, sde, sim)
            if cdt == 0:
                seq_start = mode; seq_n = None; zis = 0
            elif was_start:
                seq_start = eff_mode
                seq_n = cfg_fn(eff_mode, cycle_cap)[1]
            else:
                z10_next = sum(1 for x in hist[-10:] if x == 'ZERO')
                if zero_shock and profile_fast and (z10_next >= 2 or zis >= 2) and step >= 2:
                    nxt_n = cfg_fn(mode, bank + cdt)[1]
                    seq_n = min(10, max(seq_n if seq_n is not None else nxt_n, nxt_n))
            prev_bet = bet
        if bank < 1000: busted = True
        prof = bank - init_bank
        if prof > 0 and not busted: wins += 1
        if busted: busts += 1
        profits.append(prof); dds.append(max_dd)
        hrs.append(prof * (270.0 / max(1, len(outs))))
    hrs.sort()
    return dict(win=wins/len(seqs)*100, bust=busts/len(seqs)*100, med=statistics.median(hrs), p90=hrs[int(0.9*(len(hrs)-1))], med_raw=statistics.median(profits), max_dd=max(dds))

def make_cfg(z, t, d, zlt=None, alt_z=None, alt_t=None, alt_d=None):
    def fn(mode, cap):
        cap = max(10_000, cap)
        scale = max(0.15, min(1_000_000, cap / 1.92) / 1_000_000.0)
        if zlt is not None and cap < zlt:
            b0, n = {'ZEBRA': alt_z, 'TRANSITION': alt_t, 'DANGER': alt_d}[mode]
        else:
            b0, n = {'ZEBRA': z, 'TRANSITION': t, 'DANGER': d}[mode]
        def gsf(nn): return (math.pow(2.025, nn)-1.0)/1.025
        while n > 5 and 1000 * gsf(n) > cap: n -= 1
        max_b0 = max(1000, int(math.floor(cap / gsf(n) / 100.0) * 100))
        return max(1000, min(1_000_000, max_b0, int(js_round(b0 * scale / 100.0) * 100))), n
    return fn

cfg_apex = make_cfg((5000,8),(2500,10),(1400,10))
cfg_turbo = make_cfg((8500,7),(5000,8),(2000,9), 3_000_000, (6500,8),(4500,8),(2500,8))

all29 = [o for _, o in sessions]
nov12_outs = [o for fn, o in sessions if "2026-11-12" in fn]

print("=== BENCHMARK: v13 (Standard) vs v14-Candidate (Anti-Tunnel cas>=5) ===")
for name, rev_lim in [("v13 Standard (No Anti-Tunnel)", 99), ("v14 Candidate (Anti-Tunnel cas>=5)", 5)]:
    print(f"\n--- {name} ---")
    for prof_name, cfg, bk in [("APEX", cfg_apex, 3_800_000), ("TURBO", cfg_turbo, 4_040_371)]:
        res29 = run_causal_v14(all29, cfg, bk, True, 3_000_000, True, rev_lim)
        res12 = run_causal_v14(nov12_outs, cfg, bk, True, 3_000_000, True, rev_lim)
        print(f"  {prof_name} @ {bk/1e6:.1f}M | All 29: Win={res29['win']:.1f}% Med={res29['med']:>+10,.0f}/h MaxDD={res29['max_dd']:>9,d} | Nov12: Win={res12['win']:.0f}% Raw={res12['med_raw']:>+10,.0f} MaxDD={res12['max_dd']:>9,d}")
