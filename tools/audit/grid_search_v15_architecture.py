import json, glob, os, hashlib, statistics
from parity_ts_vs_python import exact_bet_1m, calc_net_win
from test_v14_antitunnel_bench import make_cfg
from engine_mirror import PrngDetectorMirror

def load_clean():
    paths = sorted(
        glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
        [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
        glob.glob(r'D:\Downloads\matreshka*.json') +
        glob.glob(r'D:\Downloads\quantum*.json')
    )
    skip = {'matreshka_session_2026-03-31.json', 'matreshka_session_2026-04-01 (3).json',
            'matreshka_session_2026-03-31 (1).json', 'matreshka_session_2026-03-31 (2).json', 'matreshka_session_2026-03-31 (3).json'}
    res, seen = [], set()
    for p in paths:
        if not os.path.exists(p): continue
        fn = os.path.basename(p)
        if fn in skip: continue
        with open(p, 'r', encoding='utf-8') as f: d = json.load(f)
        logs = d.get('logs', []) if isinstance(d, dict) else d
        if fn == 'matreshka_quantum_v11_2026-11-08.json': logs = logs[:22]
        outs = [e.get('input_result') or e.get('actual_outcome') or e.get('outcome') for e in logs]
        outs = [x for x in outs if x in ('RED', 'BLACK', 'ZERO')]
        h = hashlib.md5(','.join(outs).encode()).hexdigest()
        if outs and h not in seen:
            seen.add(h); res.append((fn, outs))
    return res

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

def get_matrix_w(history, window=16):
    non_zero = [h for h in history if h != 'ZERO'][-window:]
    red_count = non_zero.count('RED')
    black_count = non_zero.count('BLACK')
    max_streak_red = 0
    max_streak_black = 0
    current_streak = 0
    current_color = None
    streaks_red = []
    streaks_black = []

    for h in non_zero:
        if h == current_color:
            current_streak += 1
        else:
            if current_color == 'RED':
                streaks_red.append(current_streak)
            elif current_color == 'BLACK':
                streaks_black.append(current_streak)
            current_color = h
            current_streak = 1
        if current_color == 'RED' and current_streak > max_streak_red:
            max_streak_red = current_streak
        if current_color == 'BLACK' and current_streak > max_streak_black:
            max_streak_black = current_streak
    if current_color == 'RED':
        streaks_red.append(current_streak)
    elif current_color == 'BLACK':
        streaks_black.append(current_streak)

    avg_streak_red = sum(streaks_red) / len(streaks_red) if streaks_red else 1.5
    avg_streak_black = sum(streaks_black) / len(streaks_black) if streaks_black else 1.5

    alpha = 'NEUTRAL'
    omega = 'NEUTRAL'
    alpha_dominance = 0.5
    if non_zero:
        r_ratio = red_count / len(non_zero)
        b_ratio = black_count / len(non_zero)
        if r_ratio > 0.55:
            alpha, omega = 'RED', 'BLACK'
            alpha_dominance = r_ratio
        elif b_ratio > 0.55:
            alpha, omega = 'BLACK', 'RED'
            alpha_dominance = b_ratio
        else:
            alpha_dominance = max(r_ratio, b_ratio)

    current_active_streak = 0
    current_active_color = None
    if non_zero:
        current_active_color = non_zero[-1]
        for i in range(len(non_zero) - 1, -1, -1):
            if non_zero[i] == current_active_color:
                current_active_streak += 1
            else:
                break

    return {
        'alpha': alpha,
        'omega': omega,
        'alphaDominance': alpha_dominance,
        'maxStreakRed': max_streak_red,
        'maxStreakBlack': max_streak_black,
        'avgStreakRed': avg_streak_red,
        'avgStreakBlack': avg_streak_black,
        'currentActiveColor': current_active_color,
        'currentActiveStreak': current_active_streak,
        'non_zero_len': len(non_zero),
    }

def build_v15_predictor(window=16, pair_alt_break=True, exp_guard=True, alpha_sat=0.70):
    def predict(history):
        if not history:
            return 'RED'
        non_zero = [h for h in history if h != 'ZERO']
        if len(non_zero) < 2:
            return non_zero[-1] if non_zero else 'RED'

        matrix = get_matrix_w(history, window=window)
        cas = matrix['currentActiveStreak']
        cac = matrix['currentActiveColor']
        alpha = matrix['alpha']
        omega = matrix['omega']
        top_r = matrix['alphaDominance']

        # MPD patterns (4 spins)
        if len(non_zero) >= 4:
            L1, L2, L3, L4 = non_zero[-1], non_zero[-2], non_zero[-3], non_zero[-4]
            # Echo alternation A-B-A-B
            if L1 == L3 and L2 == L4 and L1 != L2:
                return 'BLACK' if L1 == 'RED' else 'RED'
            # 3-Streak Break Wave (A-A-A after B)
            if L1 == L2 == L3 and L4 != L1:
                return 'BLACK' if L1 == 'RED' else 'RED'

        L1, L2 = non_zero[-1], non_zero[-2]

        # Deep streak (cas >= 3) -> always fade opposite!
        if cas >= 3:
            return 'BLACK' if cac == 'RED' else 'RED'

        # Pair (cas == 2)
        if L1 == L2:
            # 1. Saturated Alpha mean reversion: break pair if dominance >= alpha_sat
            if L1 == alpha and top_r >= alpha_sat:
                return 'BLACK' if L1 == 'RED' else 'RED'

            # 2. Alternation-preceded pair: if previous spins were alternating (e.g. nz[-3] != nz[-2]),
            # alternation momentum indicates pair break back to original alternation!
            if pair_alt_break and len(non_zero) >= 3 and non_zero[-2] != non_zero[-3]:
                # check if there was alternation before the pair
                # e.g. ... A B B (or A B A B B)
                was_alternating = True
                if len(non_zero) >= 4 and non_zero[-3] == non_zero[-4]:
                    # was a doublet wave (A A B B), not pure alternation
                    was_alternating = False
                
                if was_alternating:
                    # Fade pair: return opposite!
                    return 'BLACK' if L1 == 'RED' else 'RED'

            # 3. Expected streak length guard
            if exp_guard:
                exp_len = matrix['avgStreakRed'] if L1 == 'RED' else matrix['avgStreakBlack']
                if exp_len <= 1.4:
                    return 'BLACK' if L1 == 'RED' else 'RED'

            # Default pair continuation (for doublet wave AABB or post-streak momentum AAABBB)
            return L1

        # Alternation (cas == 1)
        zm = PrngDetectorMirror.get_zebra_momentum(history)
        rec = L1 if zm['followL1'] else ('BLACK' if L1 == 'RED' else 'RED')
        if L1 == alpha and L2 == omega:
            osb = 0
            for i in range(len(non_zero) - 2, -1, -1):
                if non_zero[i] == omega:
                    osb += 1
                else:
                    break
            if osb >= 2:
                rec = alpha
        return rec

    return predict

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
    print(f'Testing Grid on {len(sessions)} clean sessions...')

    configs = [
        # (label, window, pair_alt_break, exp_guard, alpha_sat)
        ('v14.0 Baseline', 15, False, False, 0.70),
        ('v15-G1: W=15, AltBreak=True, ExpGuard=False, Sat=0.70', 15, True, False, 0.70),
        ('v15-G2: W=15, AltBreak=True, ExpGuard=True, Sat=0.70', 15, True, True, 0.70),
        ('v15-G3: W=16, AltBreak=True, ExpGuard=True, Sat=0.70', 16, True, True, 0.70),
        ('v15-G4: W=18, AltBreak=True, ExpGuard=True, Sat=0.70', 18, True, True, 0.70),
        ('v15-G5: W=20, AltBreak=True, ExpGuard=True, Sat=0.70', 20, True, True, 0.70),
        ('v15-G6: W=15, AltBreak=True, ExpGuard=True, Sat=0.68', 15, True, True, 0.68),
        ('v15-G7: W=16, AltBreak=True, ExpGuard=True, Sat=0.68', 16, True, True, 0.68),
    ]

    for p_name, cfg, init_bank in [('TURBO_HARVEST', cfg_turbo, 4_000_000), ('APEX_IDEAL', cfg_apex, 3_800_000)]:
        print(f'\n--- {p_name} ({init_bank:,} RUB) ---')
        for label, w, alt_brk, exp_g, sat in configs:
            p_fn = build_v15_predictor(window=w, pair_alt_break=alt_brk, exp_guard=exp_g, alpha_sat=sat)
            res = run_suite(sessions, p_fn, cfg, init_bank)
            
            n13 = next((v for k, v in res['sess_map'].items() if '2026-11-13' in k), None)
            n12 = next((v for k, v in res['sess_map'].items() if '2026-11-12' in k), None)
            n13_s = f"Nov13: +{n13['prof']:,} (st{n13['max_step']})" if n13 and n13['prof'] > 0 else f"Nov13: {n13['prof']:,}" if n13 else "Nov13: N/A"
            n12_s = f"Nov12: +{n12['prof']:,} (st{n12['max_step']})" if n12 and n12['prof'] > 0 else f"Nov12: {n12['prof']:,}" if n12 else "Nov12: N/A"

            print(f"{label:<55} | Net: {res['total_profit']:>10,d} ₽ | WinRate: {res['win_rate']:.1%} | MaxSt: {res['max_step']:2d} (avg {res['avg_max_step']:.1f}) | Busts: {res['busted']} | MaxDD: {res['max_dd']:>10,d} | {n13_s} | {n12_s}")
