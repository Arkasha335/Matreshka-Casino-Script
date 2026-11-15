import json, sys
sys.path.insert(0, 'tools/audit')
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror, GAME_RULES, js_round
from parity_ts_vs_python import predict_v15, exact_bet_1m, calc_net_win, cfg_1m

log_path = 'bot/logs/session_20261115_200052.jsonl'
lines = [json.loads(l) for l in open(log_path, encoding='utf-8') if l.strip()]
outs = [r['outcome'] for r in lines]
init_bank = 7_598_188

for prof in ['APEX_IDEAL', 'TURBO_HARVEST', 'SHIELD_CONSERVATIVE']:
    bank = init_bank
    step = 1
    cdt = 0
    prev_bet = None
    mode = 'ZEBRA'
    seq_start = 'ZEBRA'
    seq_n = None
    zero_in_seq = 0
    hist = []
    peak = bank
    max_dd = 0
    max_step = 1
    max_bet = 0
    series_lost = 0
    total_bets_placed = 0
    wins = 0

    for o in outs:
        if bank < 1000:
            break
        cycle_cap = bank + cdt
        zero10 = sum(1 for x in hist[-10:] if x == 'ZERO')
        is_zero_shock = prof != 'SHIELD_CONSERVATIVE' and (zero10 >= 2 or zero_in_seq >= 2)
        locked = cdt > 0 and (not is_zero_shock) and cycle_cap >= 3_000_000 and seq_start == 'ZEBRA'
        eff_mode = 'ZEBRA' if locked else mode
        b0, mode_n = cfg_1m(prof, eff_mode, cycle_cap)
        eff_n = min(10, max(seq_n, mode_n)) if (cdt > 0 and seq_n and is_zero_shock and step >= 2) else (seq_n if (cdt > 0 and seq_n) else mode_n)

        bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
        if bet > max_bet: max_bet = bet
        if step > max_step: max_step = step
        total_bets_placed += 1

        pred = predict_v15(hist, window=24)
        is_win = (o == pred and o != 'ZERO')
        net = calc_net_win(bet) if is_win else -bet
        bank += net
        if is_win: wins += 1

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
            if o == 'ZERO': zero_in_seq += 1
            is_terminal = (bet >= 1_000_000) or (eff_n is not None and step >= eff_n)
            if is_terminal:
                series_lost += 1
                cdt = 0
                step = 1
                zero_in_seq = 0
                seq_start = mode
                seq_n = None
            else:
                step += 1

        if prof != 'SHIELD_CONSERVATIVE':
            raw_m = PrngDetectorMirror.detect_mode(hist)
            z10_next = sum(1 for x in hist[-10:] if x == 'ZERO')
            nm = 'TRANSITION' if (z10_next >= 3 and raw_m == 'ZEBRA') else raw_m
            mode = nm
        else:
            mode = 'ZEBRA'

        if was_at_start and cdt > 0:
            seq_start = eff_mode
            seq_n = mode_n

    print(f"[{prof:19s}] Net: {bank - init_bank:+12,d} ₽ | WinRate: {wins/total_bets_placed*100:.1f}% | MaxStep: {max_step:2d} | MaxBet: {max_bet:9,d} ₽ | MaxDD: {max_dd:10,d} ₽ | SeriesLost: {series_lost} | Final: {bank:10,d} ₽")
