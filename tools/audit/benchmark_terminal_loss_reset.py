import sys, json, os
sys.path.insert(0, 'tools/audit')
from test_cas2_deep_study import load_clean
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror, js_round, GAME_RULES
from parity_ts_vs_python import predict_v15, exact_bet_1m, calc_net_win, cfg_1m

sessions = load_clean()

def run_backtest(profile, init_bank, reset_terminal=True):
    total_prof = 0
    busted = 0
    max_steps = []
    max_dds = []
    win_sessions = 0
    series_bust_count = 0
    sess_results = {}

    for s_name, outs in sessions:
        bank = init_bank
        step = 1
        cdt = 0
        prev_bet = None
        mode = "ZEBRA"
        prev_mode = "ZEBRA"
        sde = 999
        sim = 0
        seq_start = "ZEBRA"
        seq_n = None
        zero_in_seq = 0
        hist = []
        peak = bank
        max_dd = 0
        s_max_step = 1

        for o in outs:
            if bank < 1000:
                break
            cycle_cap = bank + cdt
            zero10 = sum(1 for x in hist[-10:] if x == "ZERO")
            is_zero_shock = profile != "SHIELD_CONSERVATIVE" and (zero10 >= 2 or zero_in_seq >= 2)
            locked = cdt > 0 and (not is_zero_shock) and cycle_cap >= 3_000_000 and seq_start == "ZEBRA"
            eff_mode = "ZEBRA" if locked else mode
            b0, mode_n = cfg_1m(profile, eff_mode, cycle_cap)
            
            if cdt > 0 and seq_n is not None:
                eff_n = min(10, max(seq_n, mode_n)) if is_zero_shock and step >= 2 else seq_n
            else:
                eff_n = mode_n

            bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
            if bet < 1000 or bet > bank:
                break
            if step > s_max_step:
                s_max_step = step

            pred = predict_v15(hist, window=24)
            is_win = (o == pred and o != "ZERO")
            net = calc_net_win(bet) if is_win else -bet
            bank += net

            if bank > peak: peak = bank
            dd = peak - bank
            if dd > max_dd: max_dd = dd

            was_at_start = (cdt == 0 or step == 1)
            hist.append(o)
            prev_bet = bet

            if is_win:
                cdt = max(0, cdt - net)
                if cdt == 0:
                    step = 1
                    zero_in_seq = 0
                    seq_start = mode
                    seq_n = None
            else:
                cdt += bet
                if o == "ZERO": zero_in_seq += 1

                # Check terminal series loss
                is_terminal = (bet >= 1_000_000) or (seq_n is not None and step >= eff_n)
                if reset_terminal and is_terminal:
                    series_bust_count += 1
                    cdt = 0
                    step = 1
                    zero_in_seq = 0
                    seq_start = mode
                    seq_n = None
                else:
                    step += 1

            if profile != "SHIELD_CONSERVATIVE":
                raw_m = PrngDetectorMirror.detect_mode(hist)
                z10_next = sum(1 for x in hist[-10:] if x == "ZERO")
                nm = "TRANSITION" if (z10_next >= 3 and raw_m == "ZEBRA") else raw_m
                prev_mode = mode if nm != mode else prev_mode
                sim = 1 if nm != mode else sim + 1
                mode = nm
                sde = 999
            else:
                mode, prev_mode, sde, sim = PrngDetectorMirror.detect_mode_with_hysteresis(hist, prev_mode, mode, sde, sim)

            if cdt == 0:
                seq_start = mode
                seq_n = None
                zero_in_seq = 0
            elif was_at_start:
                seq_start = eff_mode
                seq_n = cfg_1m(profile, eff_mode, cycle_cap)[1]
            else:
                next_zero10 = sum(1 for x in hist[-10:] if x == "ZERO")
                next_zero_shock = (profile != "SHIELD_CONSERVATIVE") and (next_zero10 >= 2 or zero_in_seq >= 2)
                if next_zero_shock and step >= 2:
                    next_mode_n = cfg_1m(profile, mode, bank + cdt)[1]
                    seq_n = min(10, max(seq_n if seq_n is not None else next_mode_n, next_mode_n))

        prof = bank - init_bank
        total_prof += prof
        max_steps.append(s_max_step)
        max_dds.append(max_dd)
        if prof > 0: win_sessions += 1
        if bank < 1000: busted += 1
        sess_results[s_name] = {'prof': prof, 'max_step': s_max_step, 'max_dd': max_dd}

    return {
        'total_profit': total_prof,
        'win_rate': win_sessions / len(sessions),
        'max_step': max(max_steps),
        'avg_max_step': sum(max_steps) / len(max_steps),
        'max_dd': max(max_dds),
        'busted': busted,
        'series_busts': series_bust_count,
        'sess_results': sess_results
    }

if __name__ == '__main__':
    print('=== TESTING TERMINAL SERIES LOSS RESET ACROSS ALL 30 SESSIONS ===\n')
    for prof, init_b in [('APEX_IDEAL', 3_800_000), ('TURBO_HARVEST', 4_000_000)]:
        print(f'--- PROFILE: {prof} (Initial Bank: {init_b:,} RUB) ---')
        r_old = run_backtest(prof, init_b, reset_terminal=False)
        r_new = run_backtest(prof, init_b, reset_terminal=True)
        
        print(f"WITHOUT Reset: Net = {r_old['total_profit']:>10,d} ₽ | WinRate = {r_old['win_rate']:.1%} | MaxSt = {r_old['max_step']} | Busts = {r_old['busted']} | MaxDD = {r_old['max_dd']:,} ₽")
        print(f"WITH Reset   : Net = {r_new['total_profit']:>10,d} ₽ | WinRate = {r_new['win_rate']:.1%} | MaxSt = {r_new['max_step']} | Busts = {r_new['busted']} | MaxDD = {r_new['max_dd']:,} ₽ | Series Lost = {r_new['series_busts']}")
        print()
