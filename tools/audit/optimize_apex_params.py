import json, glob, os, sys
sys.path.insert(0, 'tools/audit')
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror, GAME_RULES, js_round
from parity_ts_vs_python import predict_v15, exact_bet_1m, calc_net_win

# Load sessions
from benchmark_v15_1_matrix import sessions

def test_apex_variant(b0_zebra, n_zebra, b0_trans, n_trans, b0_dang, n_dang):
    tot_net = 0
    tot_series_lost = 0
    max_dd = 0
    init_b = 3_800_000

    for s_name, outs in sessions:
        bank = init_b
        step = 1
        cdt = 0
        prev_bet = None
        mode = 'ZEBRA'
        seq_start = 'ZEBRA'
        seq_n = None
        zero_in_seq = 0
        hist = []
        peak = bank
        s_dd = 0

        for o in outs:
            if bank < 1000: break
            cycle_cap = bank + cdt
            zero10 = sum(1 for x in hist[-10:] if x == 'ZERO')
            is_zero_shock = (zero10 >= 2 or zero_in_seq >= 2)
            locked = cdt > 0 and (not is_zero_shock) and cycle_cap >= 3_000_000 and seq_start == 'ZEBRA'
            eff_mode = 'ZEBRA' if locked else mode

            if eff_mode == 'ZEBRA': b0, mode_n = b0_zebra, n_zebra
            elif eff_mode == 'TRANSITION': b0, mode_n = b0_trans, n_trans
            else: b0, mode_n = b0_dang, n_dang

            scale = max(0.15, min(1_000_000, cycle_cap / 1.92) / 1_000_000)
            geom_sum = (pow(2.025, mode_n) - 1.0) / 1.025
            max_b0 = max(1000, int(cycle_cap / geom_sum / 100) * 100)
            scaled_b0 = max(1000, min(1_000_000, max_b0, round((b0 * scale) / 100) * 100))

            eff_n = min(10, max(seq_n, mode_n)) if (cdt > 0 and seq_n and is_zero_shock and step >= 2) else (seq_n if (cdt > 0 and seq_n) else mode_n)

            bet = exact_bet_1m(cdt, step, scaled_b0, eff_n, bank, prev_bet)
            pred = predict_v15(hist, window=24)
            is_win = (o == pred and o != 'ZERO')
            net = calc_net_win(bet) if is_win else -bet
            bank += net

            if bank > peak: peak = bank
            dd = peak - bank
            if dd > s_dd: s_dd = dd

            was_at_start = (cdt == 0 or step == 1)
            hist.append(o)
            prev_bet = bet

            if is_win:
                cdt = max(0, cdt - net)
                if cdt == 0:
                    step = 1; zero_in_seq = 0; seq_start = mode; seq_n = None
            else:
                cdt += bet
                if o == 'ZERO': zero_in_seq += 1
                is_terminal = (bet >= 1_000_000) or (eff_n is not None and step >= eff_n)
                if is_terminal:
                    tot_series_lost += 1
                    cdt = 0; step = 1; zero_in_seq = 0; seq_start = mode; seq_n = None
                else:
                    step += 1

            raw_m = PrngDetectorMirror.detect_mode(hist)
            z10_next = sum(1 for x in hist[-10:] if x == 'ZERO')
            mode = 'TRANSITION' if (z10_next >= 3 and raw_m == 'ZEBRA') else raw_m

            if was_at_start and cdt > 0:
                seq_start = eff_mode
                seq_n = mode_n

        tot_net += (bank - init_b)
        max_dd = max(max_dd, s_dd)

    return tot_net, tot_series_lost, max_dd

print("Evaluating APEX Parameter Variants:")
for bz in [4000, 4500, 5000]:
    for nz in [8, 9]:
        for bt in [2000, 2500]:
            net, s_lost, m_dd = test_apex_variant(bz, nz, bt, 10, 1400, 10)
            print(f"  BZ={bz:4d}, NZ={nz:1d}, BT={bt:4d} => Net={net:+11,d} ₽ | SeriesLost={s_lost} | MaxDD={m_dd:10,d} ₽")
