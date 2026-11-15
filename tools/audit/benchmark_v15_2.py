"""
v15.2 Commercial Farm Release Benchmark Suite.
Tests the v15.2 Synthesized Optimal Predictor across all available deduplicated sessions.
Evaluates APEX_FARM, TURBO_VELOCITY, and SHIELD_FORTRESS at 1M, 2.5M, 5M, 10M initial capital.
"""
import json, glob, os, sys
sys.path.insert(0, 'tools/audit')
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror, GAME_RULES, js_round
from parity_ts_vs_python import predict_v15, exact_bet_1m, calc_net_win

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json') +
    glob.glob(r'bot\logs\*.jsonl')
)

sessions = []
seen = set()
for p in paths:
    if not os.path.exists(p): continue
    fn = os.path.basename(p)
    if 'session_20260331' in fn or fn in {'matreshka_session_2026-03-31.json', 'matreshka_session_2026-04-01 (3).json',
            'matreshka_session_2026-03-31 (1).json', 'matreshka_session_2026-03-31 (2).json', 'matreshka_session_2026-03-31 (3).json'}:
        continue
    try:
        if p.endswith('.jsonl'):
            lines = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
            outs = [r.get('outcome') or r.get('input_result') for r in lines]
        else:
            d = json.load(open(p, encoding='utf-8'))
            logs = d.get('logs', []) if isinstance(d, dict) else d
            outs = [r.get('outcome') or r.get('input_result') or r.get('actual_outcome') for r in logs]
        outs = [x for x in outs if x in ('RED', 'BLACK', 'ZERO')]
        if len(outs) >= 30:
            h = hash(tuple(outs))
            if h not in seen:
                seen.add(h)
                sessions.append((fn, outs))
    except Exception:
        pass

print(f"Total deduplicated sessions loaded: {len(sessions)}")
total_spins_all = sum(len(o) for _, o in sessions)
print(f"Total spins across all sessions: {total_spins_all:,}")

def evaluate_v15_2():
    print(f"\n{'='*95}")
    print(f" EVALUATING v15.2 COMMERCIAL FARM ENGINE (Synthesized Optimal Predictor)")
    print(f"{'='*95}\n")

    profiles = [
        ('APEX_IDEAL', 'APEX FARM (Mode 2)'),
        ('TURBO_HARVEST', 'TURBO VELOCITY (Mode 1)'),
        ('SHIELD_CONSERVATIVE', 'SHIELD FORTRESS (Mode 3)')
    ]
    init_banks = [1_000_000, 2_500_000, 5_000_000, 10_000_000]

    for prof_key, prof_name in profiles:
        print(f"\n>>> PROFILE: {prof_name} [{prof_key}]")
        print(f"{'Bankroll':<12} {'Net Profit':>14} {'Win Sessions':>14} {'Max DD':>12} {'Avg WR':>10} {'Busts':>8} {'Resets':>8}")
        print("-" * 85)

        for init_b in init_banks:
            tot_net = 0
            tot_busts = 0
            tot_series_lost = 0
            tot_dd = 0
            tot_wins = 0
            tot_losses = 0
            win_sessions = 0

            for fn, outs in sessions:
                bank = init_b
                step = 1
                cdt = 0
                prev_bet = None
                mode = 'ZEBRA'
                prev_mode = 'ZEBRA'
                sde = 999
                sim = 0
                seq_start = 'ZEBRA'
                seq_n = None
                zero_in_seq = 0
                hist = []
                peak = bank
                max_dd_sess = 0
                sess_wins = 0
                sess_losses = 0

                is_fast = prof_key != 'SHIELD_CONSERVATIVE'

                for outcome in outs:
                    if bank < 1000:
                        tot_busts += 1
                        break

                    cycle_cap = bank + cdt
                    zero10 = sum(1 for x in hist[-10:] if x == 'ZERO')
                    is_zero_shock = BankrollManagerMirror.is_zero_shock_active(zero10, zero_in_seq)
                    locked = BankrollManagerMirror.should_lock_zebra(prof_key, cycle_cap, seq_start, is_zero_shock)
                    eff_mode = 'ZEBRA' if locked else mode

                    cfg = BankrollManagerMirror.get_calibrated_ladder_config(prof_key, eff_mode, cycle_cap)
                    b0 = cfg['baseBet']
                    mode_n = cfg['targetSteps']

                    if cdt > 0 and seq_n is not None:
                        if is_zero_shock and step >= 2:
                            eff_n = min(10, max(seq_n, mode_n), mode_n)
                        else:
                            eff_n = min(mode_n, seq_n)
                    else:
                        eff_n = mode_n

                    bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
                    pred = predict_v15(hist)
                    was_at_start = (cdt == 0 or step == 1)

                    is_win = False
                    if outcome == 'ZERO':
                        is_win = False
                        net_profit = -bet
                        cdt += bet
                        step += 1
                        zero_in_seq += 1
                        sess_losses += 1
                    elif outcome == pred:
                        is_win = True
                        net_profit = calc_net_win(bet)
                        cdt = max(0, cdt - net_profit)
                        if cdt == 0:
                            step = 1
                            zero_in_seq = 0
                        sess_wins += 1
                    else:
                        is_win = False
                        net_profit = -bet
                        cdt += bet
                        step += 1
                        sess_losses += 1

                    bank += net_profit
                    if bank > peak:
                        peak = bank
                    cur_dd = peak - bank
                    if cur_dd > max_dd_sess:
                        max_dd_sess = cur_dd

                    # Terminal Sequence Loss check
                    is_terminal = not is_win and BankrollManagerMirror.is_terminal_sequence_loss(
                        step - 1, seq_n, bet, GAME_RULES['MAX_BET']
                    )
                    if is_terminal:
                        cdt = 0
                        step = 1
                        zero_in_seq = 0
                        tot_series_lost += 1

                    hist.append(outcome)

                    # Update mode
                    if is_fast:
                        raw_m = PrngDetectorMirror.detect_mode_fast(hist)
                        mode = raw_m
                        prev_mode = raw_m
                        sde = 999
                    else:
                        mode, prev_mode, sde, sim = PrngDetectorMirror.detect_mode_with_hysteresis(
                            hist, prev_mode, mode, sde, sim
                        )

                    if cdt == 0:
                        seq_start = mode
                        seq_n = None
                        zero_in_seq = 0
                    elif was_at_start:
                        seq_start = eff_mode
                        seq_n = BankrollManagerMirror.get_calibrated_ladder_config(prof_key, eff_mode, cycle_cap)['targetSteps']
                    else:
                        next_zero10 = sum(1 for x in hist[-10:] if x == 'ZERO')
                        next_zero_shock = BankrollManagerMirror.is_zero_shock_active(next_zero10, zero_in_seq)
                        if next_zero_shock and step >= 2:
                            next_locked = BankrollManagerMirror.should_lock_zebra(prof_key, bank + cdt, seq_start, True)
                            next_cfg = BankrollManagerMirror.get_calibrated_ladder_config(prof_key, 'ZEBRA' if next_locked else mode, bank + cdt)
                            seq_n = min(10, max(seq_n or next_cfg['targetSteps'], next_cfg['targetSteps']))

                    prev_bet = bet

                net_sess = bank - init_b
                tot_net += net_sess
                if net_sess > 0:
                    win_sessions += 1
                if max_dd_sess > tot_dd:
                    tot_dd = max_dd_sess
                tot_wins += sess_wins
                tot_losses += sess_losses

            tot_bets = tot_wins + tot_losses
            avg_wr = (tot_wins / tot_bets * 100) if tot_bets > 0 else 0
            win_rate_sess = (win_sessions / len(sessions) * 100) if sessions else 0

            print(f"{init_b/1_000_000:>5.1f}M      {tot_net:+14,.0f} ₽ {win_sessions:>4}/{len(sessions):<3} ({win_rate_sess:4.1f}%) {tot_dd:12,.0f} ₽ {avg_wr:9.2f}% {tot_busts:8d} {tot_series_lost:8d}")

if __name__ == '__main__':
    evaluate_v15_2()
