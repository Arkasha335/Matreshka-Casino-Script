"""
Phase 3: Candidate Engine v15.2 — Prototype prediction algorithms.
Tests concrete improvements to the prediction engine against all session data.
Focus: maximizing per-spin hit rate (non-zero WR) above 50% baseline.
"""
import json, os, glob, math
from collections import defaultdict, Counter

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'bot', 'logs')
OLD_LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
OPP = {'RED': 'BLACK', 'BLACK': 'RED'}

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

# ═══════════════════════════════════════════════════════
# CANDIDATE A: "Empirical Conditional" — purely data-driven
# Uses running conditional counts to bet on whichever 
# outcome has historically followed the current (L1,L2,L3) pattern 
# more often in this session.
# ═══════════════════════════════════════════════════════

def predict_candidate_A(history, ctx):
    """Empirical 3-gram with Laplace smoothing + streak fade."""
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 5:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    
    # Hard fade on streak >= 4
    if streak >= 4:
        return OPP[color], 60
    
    # 3-gram lookup with Laplace smoothing
    trans = ctx.get('trans3', defaultdict(lambda: Counter({'RED': 1, 'BLACK': 1})))
    
    # Update transitions from latest spin
    if len(nz) >= 4:
        key = (nz[-4], nz[-3], nz[-2])
        trans[key][nz[-1]] += 1
    ctx['trans3'] = trans
    
    if len(nz) >= 3:
        key = (nz[-3], nz[-2], nz[-1])
        counts = trans.get(key, Counter({'RED': 1, 'BLACK': 1}))
        total = sum(counts.values())
        r_prob = counts.get('RED', 1) / total
        
        if r_prob > 0.52:
            return 'RED', int(50 + (r_prob - 0.5) * 60)
        elif r_prob < 0.48:
            return 'BLACK', int(50 + (0.5 - r_prob) * 60)
    
    # Fallback: alternate if recent alternation is high
    last8 = nz[-8:]
    alt = calc_alternation(last8)
    if alt >= 0.6:
        return OPP[nz[-1]], 52
    return nz[-1], 51

# ═══════════════════════════════════════════════════════
# CANDIDATE B: "Adaptive Regime" — dynamic strategy switching 
# based on rolling regime classification
# ═══════════════════════════════════════════════════════

def predict_candidate_B(history, ctx):
    """Regime-adaptive: switches between alternate, follow, and fade."""
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 4:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    
    # Hard fade on deep streak
    if streak >= 5:
        return OPP[color], 65
    
    # Compute rolling stats for regime detection
    w12 = nz[-12:] if len(nz) >= 12 else nz
    alt12 = calc_alternation(w12)
    
    w6 = nz[-6:]
    alt6 = calc_alternation(w6)
    
    # Track regime performance (which strategy won recently)
    perf = ctx.get('perf', {'alt': 0, 'fol': 0, 'fade': 0, 'n': 0})
    
    # Update perf from last prediction
    if 'last_pred' in ctx and len(nz) >= 2:
        actual = nz[-1]
        lp = ctx['last_pred']
        alt_bet = OPP[nz[-2]]
        fol_bet = nz[-2]
        
        # Decay old performance
        decay = 0.95
        perf['alt'] = perf['alt'] * decay + (1 if alt_bet == actual else -1)
        perf['fol'] = perf['fol'] * decay + (1 if fol_bet == actual else -1)
        perf['n'] += 1
    ctx['perf'] = perf
    
    # Decision
    if streak >= 3:
        pred = OPP[color]
        conf = 58
    elif streak == 2:
        # After pair: use conditional pair-break rate from session
        pair_stats = ctx.get('pair_stats', {'break': 1, 'cont': 1})
        if len(nz) >= 3 and nz[-2] == nz[-3]:
            if nz[-1] != nz[-2]:
                pair_stats['break'] += 1
            else:
                pair_stats['cont'] += 1
        ctx['pair_stats'] = pair_stats
        
        break_rate = pair_stats['break'] / (pair_stats['break'] + pair_stats['cont'])
        if break_rate > 0.52:
            pred = OPP[color]
            conf = int(50 + (break_rate - 0.5) * 50)
        else:
            pred = color
            conf = int(50 + (0.5 - break_rate) * 50)
    else:
        # Streak == 1
        if alt6 >= 0.70:
            pred = OPP[nz[-1]]
            conf = int(50 + (alt6 - 0.5) * 30)
        elif alt6 <= 0.30:
            pred = nz[-1]
            conf = 54
        else:
            # Use rolling performance to decide
            if perf['n'] > 10:
                if perf['alt'] > perf['fol'] + 1:
                    pred = OPP[nz[-1]]
                    conf = 53
                elif perf['fol'] > perf['alt'] + 1:
                    pred = nz[-1]
                    conf = 53
                else:
                    pred = OPP[nz[-1]]  # Default slight alternate
                    conf = 51
            else:
                pred = OPP[nz[-1]]
                conf = 51
    
    ctx['last_pred'] = pred
    return pred, conf

# ═══════════════════════════════════════════════════════
# CANDIDATE C: "Hybrid Ensemble" — weighted vote of
# 3-gram, alternation, alpha, and streak-fade signals
# with self-correcting weight adaptation
# ═══════════════════════════════════════════════════════

def predict_candidate_C(history, ctx):
    """Self-correcting weighted ensemble with 4 signals."""
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 5:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    L1 = nz[-1]
    
    # Hard fade at streak >= 5
    if streak >= 5:
        return OPP[color], 65
    
    weights = ctx.get('weights', {'gram3': 1.0, 'alt': 1.0, 'alpha': 1.0, 'fade': 1.0})
    signals = {}
    
    # Signal 1: 3-gram
    if len(nz) >= 3:
        trans = ctx.get('trans3c', defaultdict(lambda: Counter({'RED': 1, 'BLACK': 1})))
        if len(nz) >= 4:
            key = (nz[-4], nz[-3], nz[-2])
            trans[key][nz[-1]] += 1
        ctx['trans3c'] = trans
        
        key = (nz[-3], nz[-2], nz[-1])
        if key in trans:
            c = trans[key]
            t = sum(c.values())
            rp = c.get('RED', 1) / t
            signals['gram3'] = 'RED' if rp > 0.5 else 'BLACK'
        else:
            signals['gram3'] = OPP[L1]
    
    # Signal 2: Alternation
    w8 = nz[-8:]
    alt = calc_alternation(w8)
    signals['alt'] = OPP[L1] if alt >= 0.55 else L1
    
    # Signal 3: Alpha (dominant color in last 20)
    w20 = nz[-20:]
    rc = sum(1 for x in w20 if x == 'RED')
    signals['alpha'] = 'RED' if rc > len(w20) / 2 else 'BLACK'
    
    # Signal 4: Streak fade
    if streak >= 3:
        signals['fade'] = OPP[color]
    elif streak == 2:
        signals['fade'] = OPP[color]  # Expect pair to break
    else:
        signals['fade'] = L1  # No streak, neutral
    
    # Weighted vote
    votes = Counter()
    for sig_name, sig_pred in signals.items():
        w = weights.get(sig_name, 1.0)
        votes[sig_pred] += w
    
    pred = votes.most_common(1)[0][0]
    total_w = sum(votes.values())
    conf = int(50 + (votes[pred] / total_w - 0.5) * 40) if total_w > 0 else 50
    
    # Self-correct: update weights based on what was correct
    if 'last_signals' in ctx and len(nz) >= 2:
        actual = nz[-1]
        for sig_name, sig_pred in ctx['last_signals'].items():
            if sig_pred == actual:
                weights[sig_name] = min(3.0, weights[sig_name] * 1.02)
            else:
                weights[sig_name] = max(0.3, weights[sig_name] * 0.98)
    
    ctx['weights'] = weights
    ctx['last_signals'] = signals
    return pred, conf

# ═══════════════════════════════════════════════════════
# CANDIDATE D: "Pure Markov-3 with Streak Override"
# Simple but potentially effective: just use the 3rd-order
# Markov chain with hard streak override at 3+
# ═══════════════════════════════════════════════════════

def predict_candidate_D(history, ctx):
    """Pure Markov-3 with streak override."""
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 5:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    
    # Hard streak fade at 4+
    if streak >= 4:
        return OPP[color], 65
    
    # Build/update 3-gram transitions
    trans = ctx.get('trans3d', defaultdict(lambda: Counter()))
    if len(nz) >= 4:
        key = (nz[-4], nz[-3], nz[-2])
        trans[key][nz[-1]] += 1
    ctx['trans3d'] = trans
    
    # Predict
    if len(nz) >= 3:
        key = (nz[-3], nz[-2], nz[-1])
        if key in trans and sum(trans[key].values()) >= 3:
            counts = trans[key]
            total = sum(counts.values())
            rp = counts.get('RED', 0) / total
            if rp > 0.5:
                return 'RED', int(50 + (rp - 0.5) * 50)
            else:
                return 'BLACK', int(50 + (0.5 - rp) * 50)
    
    # Fallback: 2-gram
    if len(nz) >= 2:
        trans2 = ctx.get('trans2d', defaultdict(lambda: Counter()))
        if len(nz) >= 3:
            key2 = (nz[-3], nz[-2])
            trans2[key2][nz[-1]] += 1
        ctx['trans2d'] = trans2
        
        key2 = (nz[-2], nz[-1])
        if key2 in trans2 and sum(trans2[key2].values()) >= 5:
            counts = trans2[key2]
            total = sum(counts.values())
            rp = counts.get('RED', 0) / total
            if rp > 0.5:
                return 'RED', int(50 + (rp - 0.5) * 40)
            else:
                return 'BLACK', int(50 + (0.5 - rp) * 40)
    
    # Last resort: alternate
    return OPP[nz[-1]], 51

# ═══════════════════════════════════════════════════════
# CANDIDATE E: "No Prediction — Pure Anti-Streak"
# Ignore all patterns. Only react to streaks:
# Streak 1-2: follow.  Streak 3+: fade.
# Ultra-simple baseline.
# ═══════════════════════════════════════════════════════

def predict_candidate_E(history, ctx):
    """Pure anti-streak, no pattern matching."""
    nz = [h for h in history if h != 'ZERO']
    if not nz:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    
    if streak >= 3:
        return OPP[color], min(90, 55 + streak * 5)
    return color, 53

# ═══════════════════════════════════════════════════════
# CANDIDATE F: "Contrarian Pair Focus"
# Key insight from Phase 2 data: after pairs, continue (52.9%).
# After streak-3, break (52.9%).
# After alternation, almost random (51/49).
# Strategy: follow pairs, fade streak-3+, alternate otherwise.
# ═══════════════════════════════════════════════════════

def predict_candidate_F(history, ctx):
    """Data-aligned: follow pairs, fade 3+, alternate by default."""
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 2:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    
    if streak >= 3:
        # Data says break at 52.9%
        return OPP[color], 55
    
    if streak == 2:
        # Data says pair continues at 52.9%
        return color, 54
    
    # Streak == 1 (single / alternation)
    # Data says almost 50/50 with slight tilt to break (51.6% break)
    return OPP[nz[-1]], 51

# ═══════════════════════════════════════════════════════

def load_all_logs():
    sessions = []
    for dir_path in [LOG_DIR, OLD_LOG_DIR]:
        if not os.path.isdir(dir_path): continue
        for f in sorted(glob.glob(os.path.join(dir_path, '*.jsonl')) + glob.glob(os.path.join(dir_path, '*.json'))):
            try:
                lines = open(f, 'r', encoding='utf-8').readlines()
                outcomes = []
                for line in lines:
                    line = line.strip()
                    if not line: continue
                    obj = json.loads(line)
                    o = obj.get('outcome', obj.get('color', ''))
                    if o in ('RED', 'BLACK', 'ZERO'):
                        outcomes.append(o)
                if len(outcomes) >= 10:
                    sessions.append({'file': os.path.basename(f), 'outcomes': outcomes})
            except: pass
    return sessions


def replay_with_ctx(outcomes, predict_fn):
    history = []
    ctx = {}
    wins = 0
    losses = 0
    max_consec_loss = 0
    cur_loss = 0
    
    for out in outcomes:
        if out == 'ZERO':
            history.append(out)
            continue
        pred, _ = predict_fn(history, ctx)
        if pred == out:
            wins += 1
            cur_loss = 0
        else:
            losses += 1
            cur_loss += 1
            max_consec_loss = max(max_consec_loss, cur_loss)
        history.append(out)
    
    total = wins + losses
    return wins / total * 100 if total > 0 else 0, wins, losses, max_consec_loss


def main():
    sessions = load_all_logs()
    total_spins = sum(len(s['outcomes']) for s in sessions)
    
    print(f"{'='*100}")
    print(f"  PHASE 3: v15.2 CANDIDATE ENGINE COMPARISON — {len(sessions)} sessions, {total_spins} spins")
    print(f"{'='*100}\n")
    
    candidates = [
        ('A: Empirical 3-gram', predict_candidate_A),
        ('B: Adaptive Regime', predict_candidate_B),
        ('C: Hybrid Ensemble', predict_candidate_C),
        ('D: Pure Markov-3+Fade', predict_candidate_D),
        ('E: Pure Anti-Streak', predict_candidate_E),
        ('F: Data-Aligned', predict_candidate_F),
    ]
    
    agg = {name: {'w': 0, 'l': 0, 'mcl': 0, 'wrs': []} for name, _ in candidates}
    
    print(f"{'Session':<40}", end="")
    for name, _ in candidates:
        print(f" {name[:16]:>16}", end="")
    print()
    print("-" * 140)
    
    for sess in sessions:
        row = f"{sess['file']:<40}"
        for name, fn in candidates:
            wr, w, l, mcl = replay_with_ctx(sess['outcomes'], fn)
            agg[name]['w'] += w
            agg[name]['l'] += l
            agg[name]['mcl'] = max(agg[name]['mcl'], mcl)
            agg[name]['wrs'].append(wr)
            row += f" {wr:>15.1f}%"
        print(row)
    
    print(f"\n{'='*100}")
    print(f"  AGGREGATE RESULTS")
    print(f"{'='*100}\n")
    
    for name, a in sorted(agg.items(), key=lambda x: x[1]['w']/(x[1]['w']+x[1]['l']+1), reverse=True):
        total = a['w'] + a['l']
        wr = a['w'] / total * 100 if total > 0 else 0
        avg_wr = sum(a['wrs']) / len(a['wrs']) if a['wrs'] else 0
        best = max(a['wrs']) if a['wrs'] else 0
        worst = min(a['wrs']) if a['wrs'] else 0
        print(f"  {name:<28} WR: {wr:.2f}%  Avg: {avg_wr:.1f}%  Best: {best:.1f}%  Worst: {worst:.1f}%  "
              f"MaxConsecLoss: {a['mcl']}")
    
    # ─── Cross-validation: train on half, test on other half ───
    print(f"\n{'='*100}")
    print(f"  CROSS-VALIDATION: First half train → Second half test")
    print(f"{'='*100}\n")
    
    for sess in sessions:
        if len(sess['outcomes']) < 100:
            continue
        mid = len(sess['outcomes']) // 2
        first_half = sess['outcomes'][:mid]
        second_half = sess['outcomes'][mid:]
        
        row = f"{sess['file']:<40}"
        for name, fn in candidates:
            # "Train" on first half (build context), then test on second half
            ctx = {}
            history = []
            for out in first_half:
                if out != 'ZERO':
                    fn(history, ctx)
                history.append(out)
            
            # Test phase
            test_w = 0
            test_l = 0
            for out in second_half:
                if out == 'ZERO':
                    history.append(out)
                    continue
                pred, _ = fn(history, ctx)
                if pred == out: test_w += 1
                else: test_l += 1
                history.append(out)
            
            test_total = test_w + test_l
            test_wr = test_w / test_total * 100 if test_total > 0 else 0
            row += f" {test_wr:>15.1f}%"
        print(row)

    # ─── Deeper analysis: per-mode performance of best candidates ───
    print(f"\n{'='*100}")
    print(f"  PER-STREAK-LENGTH HIT RATE OF TOP CANDIDATES")
    print(f"{'='*100}\n")
    
    for name, fn in candidates[:4]:
        print(f"\n  >>> {name}")
        by_streak = defaultdict(lambda: [0, 0])
        for sess in sessions:
            ctx = {}
            history = []
            for out in sess['outcomes']:
                if out == 'ZERO':
                    history.append(out)
                    continue
                nz = [h for h in history if h != 'ZERO']
                s, _ = calc_current_streak(nz) if nz else (0, None)
                pred, _ = fn(history, ctx)
                if pred == out:
                    by_streak[s][0] += 1
                else:
                    by_streak[s][1] += 1
                history.append(out)
        
        for sk in sorted(by_streak.keys()):
            if sk > 10: continue
            w, l = by_streak[sk]
            t = w + l
            wr = w / t * 100 if t > 0 else 0
            bar = '█' * int(wr / 5)
            print(f"    Streak {sk:>2}: {wr:>5.1f}% ({w:>4}/{t:>4}) {bar}")


if __name__ == '__main__':
    main()
