"""
Deep Win Rate Research v15.2 — Comprehensive analysis of prediction engine accuracy.
Replays all available session logs through the exact prediction logic (PrngDetector mirror),
measures actual hit rate per state/pattern, and tests alternative strategies.
"""
import json, os, sys, math, glob
from collections import defaultdict, Counter

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'bot', 'logs')
OLD_LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')

# ─── Mirror of PrngDetector logic in Python ───

def calc_alternation(arr):
    """arr = list of 'RED'/'BLACK' outcomes (no ZERO)"""
    if len(arr) < 3:
        return 0.5
    transitions = sum(1 for i in range(1, len(arr)) if arr[i] != arr[i-1])
    return transitions / (len(arr) - 1)

def calc_current_streak(non_zero):
    if not non_zero:
        return 0, None
    streak = 1
    last = non_zero[-1]
    for i in range(len(non_zero) - 2, -1, -1):
        if non_zero[i] == last:
            streak += 1
        else:
            break
    return streak, last

def count_streaks_gte(non_zero, min_len):
    if not non_zero:
        return 0
    count = 0
    cur = 1
    last = non_zero[0]
    for i in range(1, len(non_zero)):
        if non_zero[i] == last:
            cur += 1
        else:
            if cur >= min_len:
                count += 1
            cur = 1
            last = non_zero[i]
    if cur >= min_len:
        count += 1
    return count

def get_apex_matrix(non_zero_window):
    nz = non_zero_window
    if not nz:
        return {'alpha': 'NEUTRAL', 'omega': 'NEUTRAL', 'alphaDominance': 0.5,
                'maxStreakRed': 0, 'maxStreakBlack': 0, 'avgStreakRed': 1.5, 'avgStreakBlack': 1.5,
                'currentActiveColor': None, 'currentActiveStreak': 0}
    
    rc = sum(1 for x in nz if x == 'RED')
    bc = sum(1 for x in nz if x == 'BLACK')
    
    max_sr, max_sb = 0, 0
    cur_s, cur_c = 0, None
    streaks_r, streaks_b = [], []
    
    for h in nz:
        if h == cur_c:
            cur_s += 1
        else:
            if cur_c == 'RED': streaks_r.append(cur_s)
            elif cur_c == 'BLACK': streaks_b.append(cur_s)
            cur_c = h
            cur_s = 1
        if cur_c == 'RED' and cur_s > max_sr: max_sr = cur_s
        if cur_c == 'BLACK' and cur_s > max_sb: max_sb = cur_s
    if cur_c == 'RED': streaks_r.append(cur_s)
    elif cur_c == 'BLACK': streaks_b.append(cur_s)
    
    avg_sr = sum(streaks_r) / len(streaks_r) if streaks_r else 1.5
    avg_sb = sum(streaks_b) / len(streaks_b) if streaks_b else 1.5
    
    alpha = 'NEUTRAL'
    omega = 'NEUTRAL'
    ad = 0.5
    if nz:
        rr = rc / len(nz)
        br = bc / len(nz)
        if rr > 0.55:
            alpha, omega, ad = 'RED', 'BLACK', rr
        elif br > 0.55:
            alpha, omega, ad = 'BLACK', 'RED', br
        else:
            ad = max(rr, br)
    
    cas, cac = calc_current_streak(nz)
    
    return {'alpha': alpha, 'omega': omega, 'alphaDominance': ad,
            'maxStreakRed': max_sr, 'maxStreakBlack': max_sb,
            'avgStreakRed': avg_sr, 'avgStreakBlack': avg_sb,
            'currentActiveColor': cac, 'currentActiveStreak': cas}

def get_zebra_momentum(non_zero_last6):
    nz = non_zero_last6
    if len(nz) < 4:
        return True, 55  # followL1, confidence
    alternations = sum(1 for i in range(1, len(nz)) if nz[i] != nz[i-1])
    alt_rate = alternations / (len(nz) - 1)
    if alt_rate >= 0.80:
        return False, 65
    elif alt_rate >= 0.60:
        return True, 55
    else:
        return True, 58

def predict(history_outcomes):
    """
    Exact mirror of PrngDetector.getRecommendationAndConfidence.
    history_outcomes = list of 'RED'/'BLACK'/'ZERO' strings.
    Returns (recommendation, confidence, state)
    """
    if not history_outcomes:
        return 'RED', 50, 'АНАЛИЗ'
    
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    nz_window = non_zero[-24:]  # 24-spin window
    matrix = get_apex_matrix(nz_window)
    
    rec = 'RED'
    conf = 50
    state = 'АНАЛИЗ'
    
    # MPD patterns
    if len(non_zero) >= 4:
        L1 = non_zero[-1]
        L2 = non_zero[-2]
        L3 = non_zero[-3]
        L4 = non_zero[-4]
        
        # Echo A-B-A-B
        if L1 == L3 and L2 == L4 and L1 != L2:
            rec = 'BLACK' if L1 == 'RED' else 'RED'
            return rec, 82, 'ЭХО-ПАТТЕРН'
        
        # 3-Streak Break
        if L1 == L2 and L2 == L3 and L4 != L1:
            rec = 'BLACK' if L1 == 'RED' else 'RED'
            return rec, 78, 'ВОЛНА (СЛОМ СЕРИИ)'
    
    if len(non_zero) < 2:
        rec = non_zero[-1] if non_zero else 'RED'
        return rec, conf, state
    
    L1 = non_zero[-1]
    L2 = non_zero[-2]
    
    # Deep streak fading
    if matrix['currentActiveColor'] and matrix['currentActiveStreak'] >= 3:
        rec = 'BLACK' if matrix['currentActiveColor'] == 'RED' else 'RED'
        conf = min(95, 80 + (matrix['currentActiveStreak'] - 3) * 5)
        state = 'ОТСКОК ОТ ПОТОЛКА'
    elif L1 == L2:
        # Pairs (cas == 2)
        if L1 == matrix['alpha'] and matrix['alphaDominance'] >= 0.70:
            rec = 'BLACK' if L1 == 'RED' else 'RED'
            conf = 75
            state = 'СЛОМ АЛЬФА-НАСЫЩЕНИЯ'
        else:
            rec = L1
            conf = 55
            if L1 == matrix['alpha']:
                state = 'АЛЬФА-ПАРА'
            elif L1 == matrix['omega']:
                state = 'ОМЕГА-ИМПУЛЬС'
            else:
                state = 'ПАРА (СТРАХОВКА СЕРИИ)'
    else:
        # Alternation (cas == 1)
        nz_last6 = non_zero[-6:]
        follow, zconf = get_zebra_momentum(nz_last6)
        if follow:
            rec = L1
        else:
            rec = 'BLACK' if L1 == 'RED' else 'RED'
        conf = zconf
        state = 'ЧЕРЕДОВАНИЕ (FOLLOW)' if follow else 'ЧЕРЕДОВАНИЕ (BREAK)'
    
    # Alpha emergence override
    if L1 == matrix['alpha'] and L2 == matrix['omega']:
        omega_streak_before = 0
        for i in range(len(non_zero) - 2, -1, -1):
            if non_zero[i] == matrix['omega']:
                omega_streak_before += 1
            else:
                break
        if omega_streak_before >= 2:
            rec = matrix['alpha']
            conf = 85
            state = 'ЗАРОЖДЕНИЕ АЛЬФЫ'
    
    return rec, conf, state


# ─── Alternative strategies for comparison ───

def predict_always_alternate(history_outcomes):
    """Always bet opposite of last color."""
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    if not non_zero:
        return 'RED', 50
    last = non_zero[-1]
    return ('BLACK' if last == 'RED' else 'RED'), 50

def predict_always_follow(history_outcomes):
    """Always bet same as last color."""
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    if not non_zero:
        return 'RED', 50
    return non_zero[-1], 50

def predict_alpha_only(history_outcomes):
    """Always bet on the dominant color in last 24 non-zero spins."""
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    if len(non_zero) < 10:
        return 'RED', 50
    window = non_zero[-24:]
    rc = sum(1 for x in window if x == 'RED')
    bc = len(window) - rc
    if rc > bc:
        return 'RED', 50
    elif bc > rc:
        return 'BLACK', 50
    return 'RED', 50

def predict_streak_aware(history_outcomes):
    """
    Simple heuristic:
    - Streak 1: bet same (follow)
    - Streak 2: bet same (follow)
    - Streak 3+: bet opposite (fade)
    """
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    if not non_zero:
        return 'RED', 50
    streak, color = calc_current_streak(non_zero)
    if streak >= 3:
        return ('BLACK' if color == 'RED' else 'RED'), 60
    return color, 55

def predict_conditional_pattern(history_outcomes):
    """
    Enhanced pattern-based prediction:
    - After A-B: bet A (continue alternation) - ONLY when recent altRate > 0.6
    - After A-A: bet B (expect break) - ONLY when streak not alpha-dominant  
    - After A-A-A: always bet B (strong fade)
    - After A-B-A-B: bet A (echo continues)
    - Otherwise: bet alpha color
    """
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    if len(non_zero) < 2:
        return 'RED', 50
    
    streak, color = calc_current_streak(non_zero)
    
    # Streak >= 3: always fade
    if streak >= 3:
        return ('BLACK' if color == 'RED' else 'RED'), 70
    
    L1 = non_zero[-1]
    L2 = non_zero[-2]
    
    if len(non_zero) >= 4:
        L3 = non_zero[-3]
        L4 = non_zero[-4]
        # Echo A-B-A-B: continue echo
        if L1 == L3 and L2 == L4 and L1 != L2:
            return ('BLACK' if L1 == 'RED' else 'RED'), 60
    
    # Pair (A-A): fade
    if L1 == L2:
        return ('BLACK' if L1 == 'RED' else 'RED'), 55
    
    # Alternation (A-B): continue alternation
    # Check recent alternation rate
    recent = non_zero[-8:] if len(non_zero) >= 8 else non_zero
    alt_rate = calc_alternation(recent)
    if alt_rate > 0.55:
        return ('BLACK' if L1 == 'RED' else 'RED'), 55
    else:
        return L1, 52

def predict_markov_2(history_outcomes):
    """
    2nd-order Markov chain: predict based on last 2 colors using 
    transition frequencies from entire session history.
    """
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    if len(non_zero) < 10:
        return 'RED', 50
    
    # Build transition counts: (L2, L1) -> next
    transitions = defaultdict(Counter)
    for i in range(2, len(non_zero)):
        key = (non_zero[i-2], non_zero[i-1])
        transitions[key][non_zero[i]] += 1
    
    L2 = non_zero[-2]
    L1 = non_zero[-1]
    key = (L2, L1)
    
    if key in transitions:
        counts = transitions[key]
        total = sum(counts.values())
        red_prob = counts.get('RED', 0) / total
        if red_prob > 0.5:
            return 'RED', int(50 + (red_prob - 0.5) * 100)
        else:
            return 'BLACK', int(50 + (0.5 - red_prob) * 100)
    return 'RED', 50

def predict_markov_3(history_outcomes):
    """
    3rd-order Markov chain: predict based on last 3 colors.
    """
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    if len(non_zero) < 15:
        return 'RED', 50
    
    transitions = defaultdict(Counter)
    for i in range(3, len(non_zero)):
        key = (non_zero[i-3], non_zero[i-2], non_zero[i-1])
        transitions[key][non_zero[i]] += 1
    
    key = (non_zero[-3], non_zero[-2], non_zero[-1])
    
    if key in transitions:
        counts = transitions[key]
        total = sum(counts.values())
        red_prob = counts.get('RED', 0) / total
        if red_prob > 0.5:
            return 'RED', int(50 + (red_prob - 0.5) * 100)
        else:
            return 'BLACK', int(50 + (0.5 - red_prob) * 100)
    return 'RED', 50

def predict_streaklen_fade(history_outcomes):
    """
    Use historical maximum streak length to decide when to fade.
    If current streak >= max_historic_streak * 0.7, fade.
    Otherwise follow.
    """
    non_zero = [h for h in history_outcomes if h != 'ZERO']
    if len(non_zero) < 5:
        return 'RED', 50
    
    # Find max historic streak
    max_streak = 0
    cur_s = 1
    for i in range(1, len(non_zero)):
        if non_zero[i] == non_zero[i-1]:
            cur_s += 1
            max_streak = max(max_streak, cur_s)
        else:
            cur_s = 1
    max_streak = max(max_streak, cur_s)
    
    streak, color = calc_current_streak(non_zero)
    threshold = max(3, int(max_streak * 0.6))
    
    if streak >= threshold:
        return ('BLACK' if color == 'RED' else 'RED'), 65
    elif streak >= 2:
        return color, 53  # Continue short streak
    else:
        # Alternation: bet opposite
        return ('BLACK' if color == 'RED' else 'RED'), 52


# ─── Analysis engine ───

def load_all_logs():
    """Load all available session logs."""
    sessions = []
    for dir_path in [LOG_DIR, OLD_LOG_DIR]:
        if not os.path.isdir(dir_path):
            continue
        for f in sorted(glob.glob(os.path.join(dir_path, '*.jsonl')) + glob.glob(os.path.join(dir_path, '*.json'))):
            try:
                lines = open(f, 'r', encoding='utf-8').readlines()
                spins = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    outcome = obj.get('outcome', obj.get('color', ''))
                    if outcome in ('RED', 'BLACK', 'ZERO'):
                        bet_color = obj.get('bet_color', '')
                        is_win = obj.get('is_win', None)
                        spins.append({
                            'outcome': outcome,
                            'bet_color': bet_color,
                            'is_win': is_win,
                            'balance': obj.get('bankroll', obj.get('balance', 0)),
                            'bet_amount': obj.get('bet_amount', obj.get('bet', 0)),
                            'mode': obj.get('mode', ''),
                            'step': obj.get('step', 1),
                        })
                if len(spins) >= 10:
                    sessions.append({
                        'file': os.path.basename(f),
                        'spins': spins,
                        'count': len(spins)
                    })
            except:
                pass
    return sessions

def replay_strategy(spins, predict_fn, name="engine"):
    """
    Replay a prediction strategy against actual outcomes.
    Returns detailed statistics.
    """
    history = []
    wins = 0
    losses = 0
    zero_count = 0
    
    by_state = defaultdict(lambda: {'wins': 0, 'total': 0})
    by_confidence = defaultdict(lambda: {'wins': 0, 'total': 0})
    by_streak = defaultdict(lambda: {'wins': 0, 'total': 0})
    
    consecutive_losses = 0
    max_consecutive_losses = 0
    loss_streaks = []
    
    for i, spin in enumerate(spins):
        actual = spin['outcome']
        
        if actual == 'ZERO':
            zero_count += 1
            history.append(actual)
            continue
        
        if name == "engine":
            rec, conf, state = predict_fn(history)
        else:
            rec, conf = predict_fn(history)
            state = name
        
        is_hit = (rec == actual)
        
        if is_hit:
            wins += 1
            consecutive_losses = 0
        else:
            losses += 1
            consecutive_losses += 1
            if consecutive_losses > max_consecutive_losses:
                max_consecutive_losses = consecutive_losses
        
        by_state[state]['total'] += 1
        if is_hit:
            by_state[state]['wins'] += 1
        
        conf_bucket = (conf // 10) * 10
        by_confidence[conf_bucket]['total'] += 1
        if is_hit:
            by_confidence[conf_bucket]['wins'] += 1
        
        # Track by current streak length before this spin
        non_zero_hist = [h for h in history if h != 'ZERO']
        if non_zero_hist:
            s, _ = calc_current_streak(non_zero_hist)
        else:
            s = 0
        by_streak[s]['total'] += 1
        if is_hit:
            by_streak[s]['wins'] += 1
        
        history.append(actual)
    
    total = wins + losses
    wr = (wins / total * 100) if total > 0 else 0
    
    return {
        'wins': wins,
        'losses': losses,
        'total': total,
        'zero': zero_count,
        'winrate': wr,
        'max_consecutive_losses': max_consecutive_losses,
        'by_state': dict(by_state),
        'by_confidence': dict(by_confidence),
        'by_streak': dict(by_streak),
    }


def run_full_analysis():
    sessions = load_all_logs()
    if not sessions:
        print("ERROR: No session logs found!")
        return
    
    print(f"{'='*80}")
    print(f"  DEEP WIN RATE RESEARCH — v15.2 Engine Analysis")
    print(f"  Sessions found: {len(sessions)}")
    total_spins = sum(s['count'] for s in sessions)
    print(f"  Total spins across all sessions: {total_spins}")
    print(f"{'='*80}\n")
    
    strategies = {
        'CURRENT ENGINE (v15.1)': (predict, "engine"),
        'ALWAYS ALTERNATE': (predict_always_alternate, "alt"),
        'ALWAYS FOLLOW': (predict_always_follow, "follow"),
        'ALPHA ONLY': (predict_alpha_only, "alpha"),
        'SIMPLE STREAK AWARE': (predict_streak_aware, "streak"),
        'CONDITIONAL PATTERN': (predict_conditional_pattern, "condpat"),
        'MARKOV-2': (predict_markov_2, "mk2"),
        'MARKOV-3': (predict_markov_3, "mk3"),
        'STREAKLEN FADE': (predict_streaklen_fade, "slenfade"),
    }
    
    # Aggregate results per strategy
    agg = {name: {'wins': 0, 'losses': 0, 'total': 0, 'zero': 0, 'max_cl': 0,
                   'by_state': defaultdict(lambda: {'wins': 0, 'total': 0}),
                   'by_confidence': defaultdict(lambda: {'wins': 0, 'total': 0}),
                   'by_streak': defaultdict(lambda: {'wins': 0, 'total': 0}),
                   'session_winrates': []}
           for name in strategies}
    
    # Per-session analysis for top 4 freshest sessions
    fresh_sessions = sorted(sessions, key=lambda s: s['file'], reverse=True)[:6]
    
    print(f"\n{'='*80}")
    print(f"  SECTION 1: PER-SESSION WIN RATE COMPARISON")
    print(f"{'='*80}\n")
    
    header = f"{'Session':<40}"
    for sname in strategies:
        short = sname[:12]
        header += f" {short:>12}"
    print(header)
    print("-" * len(header))
    
    for sess in sessions:
        row = f"{sess['file']:<40}"
        for sname, (sfn, stype) in strategies.items():
            r = replay_strategy(sess['spins'], sfn, stype)
            agg[sname]['wins'] += r['wins']
            agg[sname]['losses'] += r['losses']
            agg[sname]['total'] += r['total']
            agg[sname]['zero'] += r['zero']
            agg[sname]['max_cl'] = max(agg[sname]['max_cl'], r['max_consecutive_losses'])
            agg[sname]['session_winrates'].append(r['winrate'])
            
            if stype == "engine":
                for st, v in r['by_state'].items():
                    agg[sname]['by_state'][st]['wins'] += v['wins']
                    agg[sname]['by_state'][st]['total'] += v['total']
                for cb, v in r['by_confidence'].items():
                    agg[sname]['by_confidence'][cb]['wins'] += v['wins']
                    agg[sname]['by_confidence'][cb]['total'] += v['total']
            
            for sk, v in r['by_streak'].items():
                agg[sname]['by_streak'][sk]['wins'] += v['wins']
                agg[sname]['by_streak'][sk]['total'] += v['total']
            
            short = sname[:12]
            row += f" {r['winrate']:>11.1f}%"
        
        if sess['file'] in [s['file'] for s in fresh_sessions]:
            print(row)
    
    if len(sessions) > len(fresh_sessions):
        print(f"  ... ({len(sessions) - len(fresh_sessions)} more sessions omitted)")
    
    # Aggregate summary
    print(f"\n{'='*80}")
    print(f"  SECTION 2: AGGREGATE WIN RATE ACROSS ALL {len(sessions)} SESSIONS ({total_spins} spins)")
    print(f"{'='*80}\n")
    
    sorted_strats = sorted(agg.items(), key=lambda x: x[1]['wins']/max(1,x[1]['total']), reverse=True)
    
    for name, a in sorted_strats:
        wr = a['wins'] / max(1, a['total']) * 100
        avg_wr = sum(a['session_winrates']) / len(a['session_winrates']) if a['session_winrates'] else 0
        print(f"  {name:<30} WinRate: {wr:6.2f}%  (Avg session: {avg_wr:5.1f}%)  "
              f"W:{a['wins']} L:{a['losses']} MaxConsecLoss:{a['max_cl']}")
    
    # Engine-specific detailed breakdown
    eng = agg['CURRENT ENGINE (v15.1)']
    
    print(f"\n{'='*80}")
    print(f"  SECTION 3: CURRENT ENGINE — STATE BREAKDOWN")
    print(f"{'='*80}\n")
    
    state_sorted = sorted(eng['by_state'].items(), key=lambda x: x[1]['total'], reverse=True)
    for st, v in state_sorted:
        wr = v['wins'] / max(1, v['total']) * 100
        pct = v['total'] / max(1, eng['total']) * 100
        print(f"  {st:<35} WR: {wr:5.1f}%  ({v['wins']}/{v['total']})  Freq: {pct:5.1f}%")
    
    print(f"\n{'='*80}")
    print(f"  SECTION 4: CURRENT ENGINE — CONFIDENCE BUCKET ACCURACY")
    print(f"{'='*80}\n")
    
    for cb in sorted(eng['by_confidence'].keys()):
        v = eng['by_confidence'][cb]
        wr = v['wins'] / max(1, v['total']) * 100
        print(f"  Confidence {cb:>3}-{cb+9:<3}:  Actual WR: {wr:5.1f}%  ({v['wins']}/{v['total']})")
    
    print(f"\n{'='*80}")
    print(f"  SECTION 5: WIN RATE BY PRIOR STREAK LENGTH (ALL STRATEGIES)")
    print(f"{'='*80}\n")
    
    print(f"  {'Streak':<8}", end="")
    for name, _ in sorted_strats[:5]:
        print(f"  {name[:15]:>15}", end="")
    print()
    
    all_streaks = set()
    for name, a in sorted_strats[:5]:
        all_streaks.update(a['by_streak'].keys())
    
    for sk in sorted(all_streaks):
        if sk > 12:
            continue
        row = f"  {sk:<8}"
        for name, a in sorted_strats[:5]:
            v = a['by_streak'].get(sk, {'wins': 0, 'total': 0})
            if v['total'] > 0:
                wr = v['wins'] / v['total'] * 100
                row += f"  {wr:>11.1f}%({v['total']:>4})"
            else:
                row += f"  {'--':>15}"
        print(row)
    
    # ─── SECTION 6: Pattern-specific deep dive ───
    print(f"\n{'='*80}")
    print(f"  SECTION 6: DEEP PATTERN ANALYSIS")
    print(f"{'='*80}\n")
    
    # Analyze what actually happens after specific patterns across all data
    pattern_results = defaultdict(lambda: {'next_same': 0, 'next_diff': 0, 'total': 0})
    
    all_outcomes = []
    for sess in sessions:
        outcomes = [s['outcome'] for s in sess['spins'] if s['outcome'] != 'ZERO']
        all_outcomes.extend(outcomes)
        # Reset between sessions
        for i in range(4, len(outcomes)):
            L1, L2, L3, L4 = outcomes[i-1], outcomes[i-2], outcomes[i-3], outcomes[i-4]
            actual_next = outcomes[i]
            
            # Pattern: Single (A-B, alternation)
            if L1 != L2:
                key = "Alternation (A-B->?)"
                pattern_results[key]['total'] += 1
                if actual_next == L1:
                    pattern_results[key]['next_same'] += 1
                else:
                    pattern_results[key]['next_diff'] += 1
            
            # Pattern: Pair (A-A)
            if L1 == L2 and (len(outcomes) < 3 or L2 != L3):
                key = "Pair (A-A->?)"
                pattern_results[key]['total'] += 1
                if actual_next == L1:
                    pattern_results[key]['next_same'] += 1
                else:
                    pattern_results[key]['next_diff'] += 1
            
            # Streak 3
            if L1 == L2 == L3 and L4 != L1:
                key = "Streak-3 (A-A-A->?)"
                pattern_results[key]['total'] += 1
                if actual_next == L1:
                    pattern_results[key]['next_same'] += 1
                else:
                    pattern_results[key]['next_diff'] += 1
            
            # Streak 4+
            if L1 == L2 == L3 == L4:
                key = "Streak-4+ (A-A-A-A->?)"
                pattern_results[key]['total'] += 1
                if actual_next == L1:
                    pattern_results[key]['next_same'] += 1
                else:
                    pattern_results[key]['next_diff'] += 1
            
            # Echo A-B-A-B
            if L1 == L3 and L2 == L4 and L1 != L2:
                key = "Echo (A-B-A-B->?)"
                pattern_results[key]['total'] += 1
                if actual_next != L1:  # Engine bets opposite L1
                    pattern_results[key]['next_same'] += 1  # "same" means engine's bet was correct
                else:
                    pattern_results[key]['next_diff'] += 1
    
    print(f"  {'Pattern':<35}  {'Continue%':>10}  {'Break%':>10}  {'Count':>8}")
    print(f"  {'-'*70}")
    for pat, v in sorted(pattern_results.items(), key=lambda x: x[1]['total'], reverse=True):
        cont = v['next_same'] / max(1, v['total']) * 100
        brk = v['next_diff'] / max(1, v['total']) * 100
        print(f"  {pat:<35}  {cont:>9.1f}%  {brk:>9.1f}%  {v['total']:>8}")
    
    # ─── SECTION 7: Theoretical random baseline ───
    print(f"\n{'='*80}")
    print(f"  SECTION 7: ZERO FREQUENCY & SERVER ANALYSIS")
    print(f"{'='*80}\n")
    
    total_outcomes = 0
    total_zeros = 0
    total_reds = 0
    total_blacks = 0
    for sess in sessions:
        for s in sess['spins']:
            total_outcomes += 1
            if s['outcome'] == 'ZERO': total_zeros += 1
            elif s['outcome'] == 'RED': total_reds += 1
            else: total_blacks += 1
    
    print(f"  Total outcomes: {total_outcomes}")
    print(f"  RED:   {total_reds} ({total_reds/total_outcomes*100:.2f}%)")
    print(f"  BLACK: {total_blacks} ({total_blacks/total_outcomes*100:.2f}%)")
    print(f"  ZERO:  {total_zeros} ({total_zeros/total_outcomes*100:.2f}%)  (European roulette expected: 2.70%)")
    nz = total_reds + total_blacks
    print(f"  RED/BLACK ratio (no zero): {total_reds/nz*100:.2f}% / {total_blacks/nz*100:.2f}%")
    
    # Expected random winrate for RED/BLACK bet
    print(f"\n  Theoretical random WR (no prediction): {18/37*100:.2f}% = 48.65%")
    print(f"  Theoretical random WR ignoring zero:    50.00%")
    print(f"  Observed ZERO rate in our data:          {total_zeros/total_outcomes*100:.2f}%")
    observed_random = (nz * 0.5) / total_outcomes * 100
    print(f"  Effective random baseline (accounting for zero losses): {observed_random:.2f}%")
    
    print(f"\n{'='*80}")
    print(f"  END OF RESEARCH REPORT")
    print(f"{'='*80}")

if __name__ == '__main__':
    run_full_analysis()
