"""
Deep Win Rate Research Phase 2 — Advanced strategy testing.
Tests hybrid approaches, adaptive windows, and weighted ensembles.
"""
import json, os, glob, math
from collections import defaultdict, Counter

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'bot', 'logs')
OLD_LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')

def calc_alternation(arr):
    if len(arr) < 3: return 0.5
    return sum(1 for i in range(1, len(arr)) if arr[i] != arr[i-1]) / (len(arr) - 1)

def calc_current_streak(non_zero):
    if not non_zero: return 0, None
    streak = 1
    last = non_zero[-1]
    for i in range(len(non_zero) - 2, -1, -1):
        if non_zero[i] == last: streak += 1
        else: break
    return streak, last

OPP = {'RED': 'BLACK', 'BLACK': 'RED'}

# ─── Advanced strategies ───

def predict_adaptive_markov(history):
    """
    Adaptive sliding-window Markov chain.
    Uses the window size (10-50) that had the highest historical accuracy.
    """
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 15:
        return 'RED', 50
    
    best_wr = 0
    best_pred = 'RED'
    
    for window in [12, 18, 24, 36, 48]:
        if len(nz) < window + 5:
            continue
        
        # Build transition table from window
        data = nz[-window:]
        trans = defaultdict(Counter)
        for i in range(2, len(data)):
            key = (data[i-2], data[i-1])
            trans[key][data[i]] += 1
        
        key = (nz[-2], nz[-1])
        if key in trans:
            counts = trans[key]
            total = sum(counts.values())
            r_prob = counts.get('RED', 0) / total
            if r_prob > 0.5:
                pred, conf = 'RED', r_prob
            else:
                pred, conf = 'BLACK', 1.0 - r_prob
            
            # Backtest this window's accuracy on last 20 spins
            hits = 0
            tested = 0
            for i in range(max(window, len(nz)-20), len(nz)):
                if i < 2: continue
                k = (nz[i-2], nz[i-1])
                if k in trans:
                    c = trans[k]
                    t = sum(c.values())
                    rp = c.get('RED', 0) / t
                    p = 'RED' if rp > 0.5 else 'BLACK'
                    if p == nz[i]:
                        hits += 1
                    tested += 1
            
            if tested > 5:
                wr = hits / tested
                if wr > best_wr:
                    best_wr = wr
                    best_pred = pred
    
    return best_pred, int(50 + best_wr * 30)

def predict_regime_switch(history):
    """
    Detect regime (zebra vs streak) and apply different logic.
    Zebra (alt > 0.6 in last 8): bet against last.
    Streak (alt < 0.4 in last 8): bet with last.
    Transition: use Markov-2.
    """
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 5:
        return 'RED', 50
    
    last8 = nz[-8:] if len(nz) >= 8 else nz
    alt = calc_alternation(last8)
    streak, color = calc_current_streak(nz)
    
    if streak >= 4:
        # Deep streak: always fade
        return OPP[color], 65
    
    if alt >= 0.65:
        # Zebra regime: expect alternation
        return OPP[nz[-1]], 58
    elif alt <= 0.35:
        # Streak regime: follow
        return nz[-1], 56
    else:
        # Transition: use 2-gram
        if len(nz) >= 10:
            trans = defaultdict(Counter)
            for i in range(2, len(nz)):
                k = (nz[i-2], nz[i-1])
                trans[k][nz[i]] += 1
            k = (nz[-2], nz[-1])
            if k in trans:
                c = trans[k]
                t = sum(c.values())
                rp = c.get('RED', 0) / t
                return ('RED' if rp > 0.5 else 'BLACK'), 52
        return OPP[nz[-1]], 51

def predict_ensemble_vote(history):
    """
    Ensemble of 5 weak predictors, majority vote.
    """
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 5:
        return 'RED', 50
    
    votes = Counter()
    
    # 1. Alternate
    votes[OPP[nz[-1]]] += 1
    
    # 2. Follow
    votes[nz[-1]] += 1
    
    # 3. Streak fade (3+) or follow
    streak, color = calc_current_streak(nz)
    if streak >= 3:
        votes[OPP[color]] += 2  # Double weight for strong signal
    else:
        votes[color] += 1
    
    # 4. Markov-2
    if len(nz) >= 10:
        trans = defaultdict(Counter)
        for i in range(2, len(nz)):
            k = (nz[i-2], nz[i-1])
            trans[k][nz[i]] += 1
        k = (nz[-2], nz[-1])
        if k in trans:
            c = trans[k]
            t = sum(c.values())
            rp = c.get('RED', 0) / t
            v = 'RED' if rp > 0.5 else 'BLACK'
            votes[v] += 1
    
    # 5. Alpha color
    window = nz[-24:]
    rc = sum(1 for x in window if x == 'RED')
    bc = len(window) - rc
    alpha = 'RED' if rc > bc else 'BLACK'
    votes[alpha] += 1
    
    winner = votes.most_common(1)[0][0]
    total_v = sum(votes.values())
    conf = int(50 + (votes[winner] / total_v - 0.5) * 40)
    return winner, conf

def predict_bayesian_pair_fade(history):
    """
    After a pair (A-A): compute posterior probability of break using 
    session history Bayesian update. Start with 50/50 prior.
    After streak 3+: always fade.
    After alternation: follow recent momentum.
    """
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 3:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    
    if streak >= 3:
        return OPP[color], min(90, 60 + streak * 5)
    
    if streak == 2:
        # Bayesian update: how often do pairs break in this session?
        pair_breaks = 0
        pair_continues = 0
        for i in range(2, len(nz)):
            if nz[i-1] == nz[i-2]:
                if nz[i] != nz[i-1]:
                    pair_breaks += 1
                else:
                    pair_continues += 1
        
        total_pairs = pair_breaks + pair_continues
        if total_pairs > 5:
            break_rate = pair_breaks / total_pairs
            if break_rate > 0.55:
                return OPP[color], int(50 + (break_rate - 0.5) * 50)
            elif break_rate < 0.45:
                return color, int(50 + (0.5 - break_rate) * 50)
        
        return OPP[color], 52  # Default: slight fade
    
    # Streak == 1 (alternation)
    # Check alternation momentum
    last6 = nz[-6:]
    alt = calc_alternation(last6)
    if alt >= 0.70:
        return OPP[nz[-1]], 58
    else:
        return nz[-1], 53

def predict_recency_weighted(history):
    """
    Exponentially weighted recent outcomes.
    Weight recent transitions more heavily.
    """
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 5:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    if streak >= 4:
        return OPP[color], 65
    
    # Weighted alternation rate (recent outcomes weighted exponentially)
    window = nz[-12:]
    if len(window) < 3:
        return 'RED', 50
    
    weighted_alt = 0
    weight_sum = 0
    for i in range(1, len(window)):
        w = 2.0 ** (i - len(window) + 1)  # Most recent gets weight 1.0, older get less
        is_alt = 1 if window[i] != window[i-1] else 0
        weighted_alt += w * is_alt
        weight_sum += w
    
    alt_rate = weighted_alt / weight_sum if weight_sum > 0 else 0.5
    
    if alt_rate > 0.6:
        return OPP[nz[-1]], int(50 + (alt_rate - 0.5) * 30)
    elif alt_rate < 0.4:
        return nz[-1], int(50 + (0.5 - alt_rate) * 30)
    else:
        return OPP[nz[-1]], 51

def predict_optimal_retrospective(history):
    """
    Cheating oracle: knows the answer.
    Used as theoretical maximum reference.
    This is NOT a real strategy - just shows 100% WR for reference.
    We use it to compute what the actual correct bet distribution looks like.
    """
    # Can't know future, so this is just a random baseline
    nz = [h for h in history if h != 'ZERO']
    return ('RED' if len(nz) % 2 == 0 else 'BLACK'), 50

def predict_anti_engine(history):
    """Bet OPPOSITE of what the current engine recommends."""
    from deep_winrate_research import predict
    rec, conf, state = predict(history)
    return OPP.get(rec, 'RED'), conf


def load_all_logs():
    sessions = []
    for dir_path in [LOG_DIR, OLD_LOG_DIR]:
        if not os.path.isdir(dir_path): continue
        for f in sorted(glob.glob(os.path.join(dir_path, '*.jsonl')) + glob.glob(os.path.join(dir_path, '*.json'))):
            try:
                lines = open(f, 'r', encoding='utf-8').readlines()
                spins = []
                for line in lines:
                    line = line.strip()
                    if not line: continue
                    obj = json.loads(line)
                    outcome = obj.get('outcome', obj.get('color', ''))
                    if outcome in ('RED', 'BLACK', 'ZERO'):
                        spins.append(outcome)
                if len(spins) >= 10:
                    sessions.append({'file': os.path.basename(f), 'outcomes': spins})
            except: pass
    return sessions


def replay(outcomes, predict_fn, name="test"):
    history = []
    wins = 0
    losses = 0
    
    for out in outcomes:
        if out == 'ZERO':
            history.append(out)
            continue
        pred, _ = predict_fn(history)
        if pred == out: wins += 1
        else: losses += 1
        history.append(out)
    
    total = wins + losses
    return wins / total * 100 if total > 0 else 0, wins, losses


def main():
    sessions = load_all_logs()
    print(f"{'='*90}")
    print(f"  PHASE 2: ADVANCED STRATEGY COMPARISON — {len(sessions)} sessions")
    print(f"{'='*90}\n")
    
    strategies = [
        ('Adaptive Markov', predict_adaptive_markov),
        ('Regime Switch', predict_regime_switch),
        ('Ensemble Vote', predict_ensemble_vote),
        ('Bayesian Pair Fade', predict_bayesian_pair_fade),
        ('Recency Weighted', predict_recency_weighted),
    ]
    
    # Aggregate
    agg = {name: {'w': 0, 'l': 0, 'wrs': []} for name, _ in strategies}
    
    print(f"{'Session':<40}", end="")
    for name, _ in strategies:
        print(f" {name[:14]:>14}", end="")
    print()
    print("-" * 120)
    
    for sess in sessions:
        row = f"{sess['file']:<40}"
        for name, fn in strategies:
            wr, w, l = replay(sess['outcomes'], fn, name)
            agg[name]['w'] += w
            agg[name]['l'] += l
            agg[name]['wrs'].append(wr)
            row += f" {wr:>13.1f}%"
        print(row)
    
    print(f"\n{'='*90}")
    print(f"  AGGREGATE RESULTS")
    print(f"{'='*90}\n")
    
    for name, a in sorted(agg.items(), key=lambda x: x[1]['w']/(x[1]['w']+x[1]['l']+1), reverse=True):
        total = a['w'] + a['l']
        wr = a['w'] / total * 100 if total > 0 else 0
        avg_wr = sum(a['wrs']) / len(a['wrs']) if a['wrs'] else 0
        print(f"  {name:<25} Aggregate WR: {wr:.2f}%  Avg Session WR: {avg_wr:.1f}%  W:{a['w']} L:{a['l']}")
    
    # ─── SECTION: Streak length distribution analysis ───
    print(f"\n{'='*90}")
    print(f"  STREAK LENGTH DISTRIBUTION (what server actually produces)")
    print(f"{'='*90}\n")
    
    all_streaks = []
    for sess in sessions:
        nz = [x for x in sess['outcomes'] if x != 'ZERO']
        if not nz: continue
        cur_s = 1
        for i in range(1, len(nz)):
            if nz[i] == nz[i-1]:
                cur_s += 1
            else:
                all_streaks.append(cur_s)
                cur_s = 1
        all_streaks.append(cur_s)
    
    streak_dist = Counter(all_streaks)
    total_streaks = sum(streak_dist.values())
    print(f"  Total color streaks observed: {total_streaks}")
    print(f"  {'Length':<8} {'Count':>8} {'Freq%':>8} {'Expected(random)':>16} {'Ratio':>8}")
    
    for length in sorted(streak_dist.keys()):
        cnt = streak_dist[length]
        freq = cnt / total_streaks * 100
        # For fair roulette: P(streak=k) = 0.5^k * 0.5 = 0.5^(k+1) for k>=1
        # But terminal streak: P(exactly k) = (18/37)^(k-1) * (19/37)
        expected_pct = (18/37)**(length-1) * (19/37) * 100
        ratio = freq / expected_pct if expected_pct > 0 else 0
        print(f"  {length:<8} {cnt:>8} {freq:>7.2f}% {expected_pct:>15.2f}% {ratio:>7.2f}x")
    
    # ─── SECTION: What does the server ACTUALLY do after patterns? ───
    print(f"\n{'='*90}")
    print(f"  CONDITIONAL PROBABILITIES (server behavior after specific patterns)")
    print(f"{'='*90}\n")
    
    patterns = defaultdict(lambda: Counter())
    
    for sess in sessions:
        nz = [x for x in sess['outcomes'] if x != 'ZERO']
        for i in range(5, len(nz)):
            # After single (alternation): what happens?
            if nz[i-1] != nz[i-2]:
                patterns['After ALT (AB)'][nz[i]] += 1
                # More specific: after pure alternation run
                if i >= 6 and nz[i-2] != nz[i-3] and nz[i-3] != nz[i-4]:
                    patterns['After LONG ALT (ABAB)'][nz[i]] += 1
            
            # After pair
            if nz[i-1] == nz[i-2] and nz[i-2] != nz[i-3]:
                patterns['After PAIR (xAA)']['same_as_pair' if nz[i] == nz[i-1] else 'break'] += 1
            
            # After streak-3
            if nz[i-1] == nz[i-2] == nz[i-3] and nz[i-3] != nz[i-4]:
                patterns['After STREAK3 (xAAA)']['continue' if nz[i] == nz[i-1] else 'break'] += 1
            
            # After streak-4
            if nz[i-1] == nz[i-2] == nz[i-3] == nz[i-4] and (i < 5 or nz[i-4] != nz[i-5]):
                patterns['After STREAK4 (xAAAA)']['continue' if nz[i] == nz[i-1] else 'break'] += 1
            
            # After break (streak broken): is next color the breaker or original?
            if nz[i-1] != nz[i-2] and nz[i-2] == nz[i-3]:
                patterns['After BREAK (AAB)']['same_as_breaker' if nz[i] == nz[i-1] else 'return_to_original'] += 1
    
    for pat, counts in sorted(patterns.items()):
        total = sum(counts.values())
        print(f"  {pat}:")
        for outcome, cnt in counts.most_common():
            print(f"    {outcome}: {cnt} ({cnt/total*100:.1f}%)")
        print()
    
    # ─── SECTION: Zero clustering analysis ───
    print(f"\n{'='*90}")
    print(f"  ZERO CLUSTERING ANALYSIS")
    print(f"{'='*90}\n")
    
    zero_gaps = []
    for sess in sessions:
        last_zero = -1
        for i, out in enumerate(sess['outcomes']):
            if out == 'ZERO':
                if last_zero >= 0:
                    zero_gaps.append(i - last_zero)
                last_zero = i
    
    if zero_gaps:
        print(f"  Total zero gaps measured: {len(zero_gaps)}")
        print(f"  Average gap between zeros: {sum(zero_gaps)/len(zero_gaps):.1f} spins")
        print(f"  Min gap: {min(zero_gaps)}")
        print(f"  Max gap: {max(zero_gaps)}")
        print(f"  Median gap: {sorted(zero_gaps)[len(zero_gaps)//2]}")
        
        # Gaps <= 3 (clustered zeros)
        clustered = sum(1 for g in zero_gaps if g <= 3)
        print(f"  Clustered zeros (gap <= 3): {clustered} ({clustered/len(zero_gaps)*100:.1f}%)")
        print(f"  Expected for random (Poisson): ~{100*sum(0.5**k for k in range(1,4)):.1f}% if P(zero)=5%")

    print(f"\n{'='*90}")
    print(f"  END PHASE 2")
    print(f"{'='*90}")


if __name__ == '__main__':
    main()
