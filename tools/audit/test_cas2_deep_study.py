import json, glob, os, hashlib

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

def get_zebra_momentum(history):
    non_zero = [h for h in history if h != 'ZERO'][-6:]
    if len(non_zero) < 4:
        return {'followL1': True, 'confidence': 55}
    alternations = sum(1 for i in range(1, len(non_zero)) if non_zero[i] != non_zero[i - 1])
    alt_rate = alternations / (len(non_zero) - 1)
    if alt_rate >= 0.80:
        return {'followL1': False, 'confidence': 65}
    elif alt_rate >= 0.60:
        return {'followL1': True, 'confidence': 55}
    else:
        return {'followL1': True, 'confidence': 58}

def get_matrix(history, window=15):
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

def make_predictor(cas2_mode='v14', window=15):
    def predict(history):
        if not history:
            return 'RED'
        non_zero = [h for h in history if h != 'ZERO']
        if len(non_zero) < 2:
            return non_zero[-1] if non_zero else 'RED'

        matrix = get_matrix(history, window=window)
        cas = matrix['currentActiveStreak']
        cac = matrix['currentActiveColor']
        alpha = matrix['alpha']
        omega = matrix['omega']
        top_r = matrix['alphaDominance']

        # MPD patterns
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
            if cas2_mode == 'v14':
                # v14: fade if alpha saturation >= 70%, else continue
                if L1 == alpha and top_r >= 0.70:
                    return 'BLACK' if L1 == 'RED' else 'RED'
                else:
                    return L1
            elif cas2_mode == 'always_fade':
                # strictly fade pair: betting that pair breaks!
                return 'BLACK' if L1 == 'RED' else 'RED'
            elif cas2_mode == 'fade_unless_alpha_momentum':
                # fade unless Alpha has strong dominance (>= 60%) AND expected streak >= 2.0
                exp_len = matrix['avgStreakRed'] if L1 == 'RED' else matrix['avgStreakBlack']
                if L1 == alpha and top_r >= 0.60 and top_r < 0.70 and exp_len >= 2.0:
                    return L1
                return 'BLACK' if L1 == 'RED' else 'RED'
            elif cas2_mode == 'fade_in_zebra':
                # fade if zebra momentum says alternation (alt_rate >= 0.60)
                zm = get_zebra_momentum(history)
                # if zm is follow alternation, fade pair
                if not zm['followL1']:
                    return 'BLACK' if L1 == 'RED' else 'RED'
                else:
                    return L1
            elif cas2_mode == 'exp_streak_fade':
                # fade if current streak (2) >= avg streak length
                exp_len = matrix['avgStreakRed'] if L1 == 'RED' else matrix['avgStreakBlack']
                if exp_len <= 2.0:
                    return 'BLACK' if L1 == 'RED' else 'RED'
                else:
                    if L1 == alpha and top_r >= 0.70:
                        return 'BLACK' if L1 == 'RED' else 'RED'
                    return L1
            elif cas2_mode == 'continue_unless_saturated':
                if L1 == alpha and top_r >= 0.65:
                    return 'BLACK' if L1 == 'RED' else 'RED'
                return L1
            else:
                return 'BLACK' if L1 == 'RED' else 'RED'

        # Alternation (cas == 1)
        zm = get_zebra_momentum(history)
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

if __name__ == '__main__':
    sessions = load_clean()
    total_spins = sum(len(s[1]) for s in sessions)
    print(f'Loaded {len(sessions)} clean sessions ({total_spins} spins).')

    variants = [
        ('v14.0 (Base: continue pair unless alpha >= 70%)', 'v14', 15),
        ('v15-Cand1 (Always Fade pair: cas>=2 -> opposite)', 'always_fade', 15),
        ('v15-Cand2 (Fade unless Alpha Mom: 60-70% & E[L]>=2.0)', 'fade_unless_alpha_momentum', 15),
        ('v15-Cand3 (Exp Streak Fade: fade if E[L] <= 2.0)', 'exp_streak_fade', 15),
        ('v15-Cand4 (Fade in Zebra momentum)', 'fade_in_zebra', 15),
        ('v15-Cand5 (Alpha Saturation threshold 65%)', 'continue_unless_saturated', 15),
    ]

    print('\n=== PREDICTOR RAW ACCURACY & MAX LOSS STREAK ===')
    for label, mode, w in variants:
        pred_fn = make_predictor(mode, w)
        total_wins = 0
        total_non_zero = 0
        max_ls_list = []
        
        for name, outs in sessions:
            hist = []
            curr_ls = 0
            s_max_ls = 0
            for o in outs:
                p = pred_fn(hist)
                if o != 'ZERO':
                    total_non_zero += 1
                    if p == o:
                        total_wins += 1
                        curr_ls = 0
                    else:
                        curr_ls += 1
                        if curr_ls > s_max_ls: s_max_ls = curr_ls
                else:
                    curr_ls += 1
                    if curr_ls > s_max_ls: s_max_ls = curr_ls
                hist.append(o)
            max_ls_list.append(s_max_ls)
            
        winrate = total_wins / total_spins
        nz_winrate = total_wins / total_non_zero
        avg_max_ls = sum(max_ls_list) / len(max_ls_list)
        peak_ls = max(max_ls_list)
        print(f'{label:<52} | Raw: {winrate:.2%} | Non-Zero: {nz_winrate:.2%} | Peak Loss Streak: {peak_ls:2d} | Avg MaxLS: {avg_max_ls:.2f}')
