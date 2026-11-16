"""
Comprehensive Audit & Head-to-Head Comparison:
v15.0 vs v15.1 vs v15.2 across all 48 real sessions (6,069 spins).
Evaluates both Pure Prediction Accuracy and Financial APEX Farm Execution.
"""
import glob, json, math, os, sys
from collections import defaultdict, Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror, GAME_RULES, js_round
from parity_ts_vs_python import exact_bet_1m, calc_net_win

OPP = {'RED': 'BLACK', 'BLACK': 'RED'}

# --- 1. Load All 48 Unique Real Sessions ---
def load_all_unique_sessions():
    import hashlib
    all_files = []
    for p in sorted(glob.glob(r'bot\logs\*.jsonl')):
        all_files.append(('bot_log', p))
    if os.path.exists(r'tools\audit\normalized_spins.json'):
        all_files.append(('normalized', r'tools\audit\normalized_spins.json'))
    for p in sorted(glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json')):
        all_files.append(('quantum_storage', p))
    for p in sorted(glob.glob(r'D:\Downloads\matreshka*.json')):
        all_files.append(('downloads_matreshka', p))
    for p in sorted(glob.glob(r'D:\Downloads\quantum*.json')):
        all_files.append(('downloads_quantum', p))

    sessions = []
    seen = set()

    # 1. bot logs first
    for ftype, p in all_files:
        if ftype == 'bot_log':
            try:
                lines = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
                outs = [r.get('outcome') for r in lines if r.get('outcome') in ('RED', 'BLACK', 'ZERO')]
                if len(outs) >= 5:
                    h = hashlib.md5(','.join(outs).encode()).hexdigest()
                    if h not in seen:
                        seen.add(h)
                        sessions.append({
                            'source': 'bot_log',
                            'file': os.path.basename(p),
                            'outcomes': outs,
                            'live_lines': lines
                        })
            except Exception: pass

    # 2. normalized
    for ftype, p in all_files:
        if ftype == 'normalized':
            try:
                data = json.load(open(p, encoding='utf-8'))
                by_sess = defaultdict(list)
                for d in data:
                    sid = d.get('session_id', 'unknown')
                    o = d.get('outcome')
                    if o in ('RED', 'BLACK', 'ZERO'):
                        by_sess[sid].append(o)
                for sid, outs in sorted(by_sess.items()):
                    if len(outs) >= 10:
                        h = hashlib.md5(','.join(outs).encode()).hexdigest()
                        if h not in seen:
                            seen.add(h)
                            sessions.append({
                                'source': 'normalized',
                                'file': f'[NORM] {sid}',
                                'outcomes': outs,
                                'live_lines': None
                            })
            except Exception: pass

    # 3. historical downloads
    for ftype, p in all_files:
        if ftype in ('quantum_storage', 'downloads_matreshka', 'downloads_quantum'):
            try:
                d = json.load(open(p, encoding='utf-8'))
                logs = d.get('logs', []) if isinstance(d, dict) else d
                outs = [r.get('outcome') or r.get('input_result') or r.get('actual_outcome') for r in logs]
                outs = [x for x in outs if x in ('RED', 'BLACK', 'ZERO')]
                if len(outs) >= 15:
                    h = hashlib.md5(','.join(outs).encode()).hexdigest()
                    if h not in seen:
                        seen.add(h)
                        sessions.append({
                            'source': 'historical',
                            'file': os.path.basename(p),
                            'outcomes': outs,
                            'live_lines': logs if isinstance(logs, list) else None
                        })
            except Exception: pass

    return sessions

# --- 2. Predictor Definitions ---

def predict_v15_0(history):
    """v15.0 & v15.1 Predictor: Rule-based MPD + Hardcoded cas>=3 fade + Alpha/Omega + Zebra momentum."""
    if not history: return 'RED'
    nz = [h for h in history if h != 'ZERO']
    if not nz: return 'RED'

    # MPD
    if len(nz) >= 4:
        L1, L2, L3, L4 = nz[-1], nz[-2], nz[-3], nz[-4]
        if L1 == L3 and L2 == L4 and L1 != L2:
            return OPP[L1]
        if L1 == L2 == L3 and L4 != L1:
            return OPP[L1]

    if len(nz) < 2:
        return nz[-1]

    L1, L2 = nz[-1], nz[-2]

    # Apex matrix window 24
    win_nz = nz[-24:]
    rc = win_nz.count('RED')
    bc = len(win_nz) - rc
    alpha = 'RED' if win_nz and rc / len(win_nz) > 0.55 else ('BLACK' if win_nz and bc / len(win_nz) > 0.55 else 'NEUTRAL')
    omega = 'BLACK' if alpha == 'RED' else ('RED' if alpha == 'BLACK' else 'NEUTRAL')
    alpha_dom = max(rc, bc) / len(win_nz) if win_nz else 0.5

    cas = 1
    cac = nz[-1]
    for i in range(len(nz) - 2, -1, -1):
        if nz[i] == cac: cas += 1
        else: break

    # 1. Deep streak fading
    if cas >= 3:
        rec = OPP[cac]
    elif L1 == L2:
        if L1 == alpha and alpha_dom >= 0.70:
            rec = OPP[L1]
        else:
            rec = L1
    else:
        zm = PrngDetectorMirror.get_zebra_momentum(history)
        rec = L1 if zm['followL1'] else OPP[L1]

    # Alpha emergence
    if L1 == alpha and L2 == omega:
        osb = 0
        for i in range(len(nz) - 2, -1, -1):
            if nz[i] == omega: osb += 1
            else: break
        if osb >= 2:
            rec = alpha

    return rec

def predict_v15_1(history):
    """v15.1 uses identical predictor to v15.0."""
    return predict_v15_0(history)

def predict_v15_2(history):
    """v15.2 Synthesized Optimal Predictor (empirical session transitions)."""
    rec, _, _ = PrngDetectorMirror.get_recommendation_and_confidence(history)
    return rec

# --- 3. Staking Configurations ---

def get_cfg_v15_0(profile, mode, cap):
    """v15.0 FINAL APEX Matrix."""
    cap = max(10_000, cap)
    if profile == 'SHIELD_CONSERVATIVE':
        target_steps = 10
        nominal_b0 = 1700 if mode == 'ZEBRA' else (1200 if mode == 'TRANSITION' else 1000)
    elif profile == 'TURBO_HARVEST':
        if cap >= 3_000_000:
            if mode == 'ZEBRA': nominal_b0, target_steps = 8500, 7
            elif mode == 'TRANSITION': nominal_b0, target_steps = 5000, 8
            else: nominal_b0, target_steps = 2000, 9
        else:
            target_steps = 8
            nominal_b0 = 6500 if mode == 'ZEBRA' else (4500 if mode == 'TRANSITION' else 2500)
    else: # APEX_IDEAL
        if mode == 'ZEBRA': nominal_b0, target_steps = 5000, 8
        elif mode == 'TRANSITION': nominal_b0, target_steps = 2500, 10
        else: nominal_b0, target_steps = 1400, 10
    return {'baseBet': nominal_b0, 'targetSteps': target_steps}

def get_cfg_v15_1_2(profile, mode, cap):
    """v15.1 & v15.2 Commercial Farm Matrix."""
    return BankrollManagerMirror.get_calibrated_ladder_config(profile, mode, cap)

# --- 4. Simulation Engine ---

def simulate_session(outs, predict_fn, cfg_fn, init_bank=7_500_000, profile='APEX_IDEAL'):
    bank = init_bank
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
    max_dd = 0

    wins = 0
    losses = 0
    bets_placed = []
    closing_steps = []
    max_step_reached = 1
    terminal_resets = 0

    is_fast = profile != 'SHIELD_CONSERVATIVE'

    for outcome in outs:
        if bank < 1000:
            break

        cycle_cap = bank + cdt
        zero10 = sum(1 for x in hist[-10:] if x == 'ZERO')
        is_zero_shock = (zero10 >= 2 or zero_in_seq >= 2)
        locked = (profile != 'SHIELD_CONSERVATIVE' and cycle_cap >= 3000000 and seq_start == 'ZEBRA' and not is_zero_shock)
        eff_mode = 'ZEBRA' if locked else mode

        cfg = cfg_fn(profile, eff_mode, cycle_cap)
        if isinstance(cfg, tuple):
            b0, mode_n = cfg[0], cfg[1]
        else:
            b0, mode_n = cfg['baseBet'], cfg['targetSteps']

        if cdt > 0 and seq_n is not None:
            if is_zero_shock and step >= 2:
                eff_n = min(10, max(seq_n, mode_n), mode_n)
            else:
                eff_n = min(mode_n, seq_n)
        else:
            eff_n = mode_n

        bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
        pred = predict_fn(hist)
        was_at_start = (cdt == 0 or step == 1)

        current_bet_step = step
        if current_bet_step > max_step_reached:
            max_step_reached = current_bet_step

        bets_placed.append(bet)

        is_win = False
        if outcome == 'ZERO':
            is_win = False
            net_profit = -bet
            cdt += bet
            step += 1
            zero_in_seq += 1
            losses += 1
        elif outcome == pred:
            is_win = True
            net_profit = calc_net_win(bet)
            cdt = max(0, cdt - net_profit)
            if cdt == 0:
                step = 1
                zero_in_seq = 0
            closing_steps.append(current_bet_step)
            wins += 1
        else:
            is_win = False
            net_profit = -bet
            cdt += bet
            step += 1
            losses += 1

        bank += net_profit
        if bank > peak: peak = bank
        cur_dd = peak - bank
        if cur_dd > max_dd: max_dd = cur_dd

        # Terminal sequence loss check
        is_terminal = not is_win and BankrollManagerMirror.is_terminal_sequence_loss(
            current_bet_step, seq_n, bet, GAME_RULES['MAX_BET']
        )
        if is_terminal:
            cdt = 0
            step = 1
            zero_in_seq = 0
            terminal_resets += 1

        hist.append(outcome)

        if is_fast:
            raw_m = PrngDetectorMirror.detect_mode(hist)
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
            start_cfg = cfg_fn(profile, eff_mode, cycle_cap)
            seq_n = start_cfg[1] if isinstance(start_cfg, tuple) else start_cfg['targetSteps']
        else:
            next_zero10 = sum(1 for x in hist[-10:] if x == 'ZERO')
            next_zero_shock = (next_zero10 >= 2 or zero_in_seq >= 2)
            if next_zero_shock and step >= 2:
                next_locked = (profile != 'SHIELD_CONSERVATIVE' and (bank + cdt) >= 3000000 and seq_start == 'ZEBRA' and not True)
                next_cfg = cfg_fn(profile, 'ZEBRA' if next_locked else mode, bank + cdt)
                next_n = next_cfg[1] if isinstance(next_cfg, tuple) else next_cfg['targetSteps']
                seq_n = min(10, max(seq_n or next_n, next_n))

        prev_bet = bet

    avg_bet = sum(bets_placed) / len(bets_placed) if bets_placed else 0
    avg_win_step = sum(closing_steps) / len(closing_steps) if closing_steps else 0
    net_profit = bank - init_bank
    wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

    return {
        'net_profit': net_profit,
        'final_bank': bank,
        'wr': wr,
        'wins': wins,
        'losses': losses,
        'total_spins': len(bets_placed),
        'avg_bet': avg_bet,
        'avg_win_step': avg_win_step,
        'max_step': max_step_reached,
        'max_dd': max_dd,
        'resets': terminal_resets,
        'is_bust': bank < 1000
    }

if __name__ == '__main__':
    sessions = load_all_unique_sessions()
    print(f"Total Unique Sessions Loaded: {len(sessions)}")
    total_spins = sum(len(s['outcomes']) for s in sessions)
    print(f"Total Spins Across All Sessions: {total_spins:,}")

    bot_sessions = [s for s in sessions if s['source'] == 'bot_log']
    hist_sessions = [s for s in sessions if s['source'] != 'bot_log']

    print(f"  - Real Bot Sessions: {len(bot_sessions)} ({sum(len(s['outcomes']) for s in bot_sessions):,} spins)")
    print(f"  - Historical Sessions: {len(hist_sessions)} ({sum(len(s['outcomes']) for s in hist_sessions):,} spins)")

    # 1. LIVE BOT RUN STATISTICS (as recorded in jsonl)
    print("\n" + "="*110)
    print(" 1. ACTUAL LIVE BOT SESSIONS PERFORMANCE (EMPIRICAL RUN LOGS)")
    print("="*110)
    print(f"{'Session File':<32} {'Spins':>6} {'WR (%)':>8} {'Avg Step':>9} {'Max Step':>9} {'Avg Bet (₽)':>13} {'Net Profit (₽)':>16}")
    print("-" * 110)

    live_tot_spins = 0
    live_tot_wins = 0
    live_all_steps = []
    live_all_bets = []
    live_tot_net = 0
    live_max_step_overall = 0

    for s in bot_sessions:
        lines = s['live_lines']
        if not lines: continue
        spins = len(lines)
        wins = sum(1 for l in lines if l.get('is_win'))
        wr = (wins / spins * 100) if spins else 0
        bets = [l.get('bet_amount', 0) for l in lines]
        avg_bet = sum(bets) / len(bets) if bets else 0
        
        # reconstruct placed steps
        prev_step = 1
        closing_steps = []
        max_step = 1
        for i, l in enumerate(lines):
            placed_step = 1 if i == 0 else prev_step
            if placed_step > max_step: max_step = placed_step
            if l.get('is_win'):
                closing_steps.append(placed_step)
            prev_step = l.get('step', 1)

        avg_step = sum(closing_steps) / len(closing_steps) if closing_steps else 1.0
        start_b = lines[0].get('bankroll', 0) - (lines[0].get('net_profit', 0) if lines[0].get('is_win') else -lines[0].get('bet_amount', 0))
        end_b = lines[-1].get('bankroll', 0)
        net = end_b - start_b

        live_tot_spins += spins
        live_tot_wins += wins
        live_all_steps.extend(closing_steps)
        live_all_bets.extend(bets)
        live_tot_net += net
        if max_step > live_max_step_overall: live_max_step_overall = max_step

        print(f"{s['file']:<32} {spins:>6} {wr:>7.1f}% {avg_step:>9.2f} {max_step:>9} {avg_bet:>13,.0f} {net:>+16,.0f}")

    live_wr_overall = (live_tot_wins / live_tot_spins * 100) if live_tot_spins else 0
    live_avg_step_overall = (sum(live_all_steps) / len(live_all_steps)) if live_all_steps else 0
    live_avg_bet_overall = (sum(live_all_bets) / len(live_all_bets)) if live_all_bets else 0

    print("-" * 110)
    print(f"{'OVERALL LIVE BOT TOTALS:':<32} {live_tot_spins:>6} {live_wr_overall:>7.1f}% {live_avg_step_overall:>9.2f} {live_max_step_overall:>9} {live_avg_bet_overall:>13,.0f} {live_tot_net:>+16,.0f}")

    # 2. PURE PREDICTOR ACCURACY COMPARISON (v15.0 vs v15.1 vs v15.2)
    print("\n" + "="*110)
    print(" 2. PURE PREDICTION ACCURACY AUDIT: v15.0 vs v15.1 vs v15.2")
    print("="*110)

    for subset_name, subset in [("ALL 48 SESSIONS (6,069 spins)", sessions),
                                ("13 REAL BOT SESSIONS (2,799 spins)", bot_sessions),
                                ("35 HISTORICAL SESSIONS (3,270 spins)", hist_sessions)]:
        print(f"\n--- Subgroup: {subset_name} ---")
        print(f"{'Model / Version':<25} {'Total Bets':>12} {'Wins':>8} {'Losses':>8} {'Total WR':>10} {'Non-Zero WR':>14} {'z-score':>10}")
        print("-" * 95)

        for v_name, pred_fn in [('v15.0 FINAL APEX', predict_v15_0),
                                ('v15.1 Commercial Farm', predict_v15_1),
                                ('v15.2 Synthesized Optimal', predict_v15_2)]:
            tot_bets = 0
            tot_nz_bets = 0
            tot_wins = 0

            for s in subset:
                outs = s['outcomes']
                hist = []
                for o in outs:
                    pred = pred_fn(hist)
                    tot_bets += 1
                    if o != 'ZERO':
                        tot_nz_bets += 1
                    if o == pred:
                        tot_wins += 1
                    hist.append(o)

            total_wr = (tot_wins / tot_bets * 100) if tot_bets else 0
            nz_wr = (tot_wins / tot_nz_bets * 100) if tot_nz_bets else 0
            p_hat = tot_wins / tot_nz_bets if tot_nz_bets else 0.5
            se = math.sqrt(0.25 / tot_nz_bets) if tot_nz_bets else 1.0
            z = (p_hat - 0.50) / se if se > 0 else 0

            print(f"{v_name:<25} {tot_bets:>12,d} {tot_wins:>8,d} {tot_bets - tot_wins:>8,d} {total_wr:>9.2f}% {nz_wr:>13.2f}% {z:>+10.2f}")

    # 3. FINANCIAL APEX FARM PERFORMANCE (Identical Capital 7.5M RUB, APEX_IDEAL profile)
    print("\n" + "="*110)
    print(" 3. FINANCIAL APEX FARM AUDIT: v15.0 vs v15.1 vs v15.2 (All 48 Sessions, Capital = 7.5M ₽)")
    print("="*110)
    print(f"{'Engine Version':<25} {'Net Profit (₽)':>16} {'Win Sess':>12} {'WR (%)':>8} {'Avg Step':>9} {'Max Step':>9} {'Avg Bet (₽)':>12} {'Max DD (₽)':>14} {'Resets':>8} {'Busts':>6}")
    print("-" * 118)

    versions = [
        ('v15.0 FINAL APEX', predict_v15_0, get_cfg_v15_0),
        ('v15.1 Commercial Farm', predict_v15_1, get_cfg_v15_1_2),
        ('v15.2 Synthesized Farm', predict_v15_2, get_cfg_v15_1_2),
    ]

    for v_name, p_fn, c_fn in versions:
        tot_net = 0
        win_sess = 0
        all_wins = 0
        all_losses = 0
        all_bets = []
        all_closing_steps = []
        max_step_overall = 1
        max_dd_overall = 0
        tot_resets = 0
        tot_busts = 0

        for s in sessions:
            res = simulate_session(s['outcomes'], p_fn, c_fn, init_bank=7_500_000, profile='APEX_IDEAL')
            tot_net += res['net_profit']
            if res['net_profit'] > 0: win_sess += 1
            all_wins += res['wins']
            all_losses += res['losses']
            if res['avg_bet'] > 0: all_bets.append(res['avg_bet'])
            if res['avg_win_step'] > 0: all_closing_steps.append(res['avg_win_step'])
            if res['max_step'] > max_step_overall: max_step_overall = res['max_step']
            if res['max_dd'] > max_dd_overall: max_dd_overall = res['max_dd']
            tot_resets += res['resets']
            if res['is_bust']: tot_busts += 1

        overall_wr = (all_wins / (all_wins + all_losses) * 100) if (all_wins + all_losses) else 0
        overall_avg_step = (sum(all_closing_steps) / len(all_closing_steps)) if all_closing_steps else 0
        overall_avg_bet = (sum(all_bets) / len(all_bets)) if all_bets else 0

        print(f"{v_name:<25} {tot_net:>+16,.0f} {win_sess:>7}/{len(sessions):<4} {overall_wr:>7.2f}% {overall_avg_step:>9.2f} {max_step_overall:>9} {overall_avg_bet:>12,.0f} {max_dd_overall:>14,.0f} {tot_resets:>8} {tot_busts:>6}")

