"""
Phase 4: Complete Combined Research — ALL available data.
Includes normalized_spins.json + bot/logs/*.jsonl.
Tests all candidates and generates final recommendations.
"""
import json, os, glob, math
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(BASE, 'bot', 'logs')
NORM_FILE = os.path.join(BASE, 'tools', 'audit', 'normalized_spins.json')
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

def load_all_sessions():
    sessions = []
    
    # Load from bot/logs
    for f in sorted(glob.glob(os.path.join(LOG_DIR, '*.jsonl'))):
        try:
            lines = open(f, 'r', encoding='utf-8').readlines()
            outcomes = []
            for line in lines:
                line = line.strip()
                if not line: continue
                obj = json.loads(line)
                o = obj.get('outcome', '')
                if o in ('RED', 'BLACK', 'ZERO'):
                    outcomes.append(o)
            if len(outcomes) >= 10:
                sessions.append({'file': os.path.basename(f), 'outcomes': outcomes})
        except: pass
    
    # Load from normalized_spins.json
    if os.path.exists(NORM_FILE):
        with open(NORM_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        by_session = defaultdict(list)
        for d in data:
            sid = d.get('session_id', 'unknown')
            o = d.get('outcome', '')
            if o in ('RED', 'BLACK', 'ZERO'):
                by_session[sid].append(o)
        
        for sid, outcomes in sorted(by_session.items()):
            if len(outcomes) >= 10:
                sessions.append({'file': f'[NORM] {sid}', 'outcomes': outcomes})
    
    return sessions

# ─── Current engine mirror ───
def predict_current_engine(history, ctx):
    nz = [h for h in history if h != 'ZERO']
    
    if not nz:
        return 'RED', 50
    
    # Apex matrix (24-window)
    nzw = nz[-24:]
    rc = sum(1 for x in nzw if x == 'RED')
    bc = len(nzw) - rc
    alpha = 'NEUTRAL'
    omega = 'NEUTRAL'
    ad = 0.5
    if nzw:
        rr = rc / len(nzw)
        br = bc / len(nzw)
        if rr > 0.55: alpha, omega, ad = 'RED', 'BLACK', rr
        elif br > 0.55: alpha, omega, ad = 'BLACK', 'RED', br
        else: ad = max(rr, br)
    
    cas, cac = calc_current_streak(nzw)
    
    rec, conf, state = 'RED', 50, 'АНАЛИЗ'
    
    # MPD
    if len(nz) >= 4:
        L1, L2, L3, L4 = nz[-1], nz[-2], nz[-3], nz[-4]
        if L1 == L3 and L2 == L4 and L1 != L2:
            return OPP[L1], 82
        if L1 == L2 == L3 and L4 != L1:
            return OPP[L1], 78
    
    if len(nz) < 2:
        return nz[-1], 50
    
    L1, L2 = nz[-1], nz[-2]
    
    if cac and cas >= 3:
        rec = OPP[cac]
        conf = min(95, 80 + (cas - 3) * 5)
    elif L1 == L2:
        if L1 == alpha and ad >= 0.70:
            rec = OPP[L1]
            conf = 75
        else:
            rec = L1
            conf = 55
    else:
        nz6 = nz[-6:]
        alt6 = calc_alternation(nz6)
        if alt6 >= 0.80:
            rec = OPP[L1]
            conf = 65
        elif alt6 >= 0.60:
            rec = L1
            conf = 55
        else:
            rec = L1
            conf = 58
    
    # Alpha emergence override
    if L1 == alpha and L2 == omega:
        osb = 0
        for i in range(len(nz) - 2, -1, -1):
            if nz[i] == omega: osb += 1
            else: break
        if osb >= 2:
            rec = alpha
            conf = 85
    
    return rec, conf

# ─── Best candidates from Phase 3 ───

def predict_B_adaptive(history, ctx):
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 4: return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    if streak >= 5: return OPP[color], 65
    
    w6 = nz[-6:]
    alt6 = calc_alternation(w6)
    
    perf = ctx.get('perf', {'alt': 0, 'fol': 0, 'n': 0})
    if 'last_pred' in ctx and len(nz) >= 2:
        actual = nz[-1]
        decay = 0.95
        alt_bet = OPP[nz[-2]]
        fol_bet = nz[-2]
        perf['alt'] = perf['alt'] * decay + (1 if alt_bet == actual else -1)
        perf['fol'] = perf['fol'] * decay + (1 if fol_bet == actual else -1)
        perf['n'] += 1
    ctx['perf'] = perf
    
    if streak >= 3:
        pred = OPP[color]
        conf = 58
    elif streak == 2:
        pair_stats = ctx.get('pair_stats', {'break': 1, 'cont': 1})
        if len(nz) >= 3 and nz[-2] == nz[-3]:
            if nz[-1] != nz[-2]: pair_stats['break'] += 1
            else: pair_stats['cont'] += 1
        ctx['pair_stats'] = pair_stats
        break_rate = pair_stats['break'] / (pair_stats['break'] + pair_stats['cont'])
        if break_rate > 0.52:
            pred = OPP[color]
        else:
            pred = color
        conf = 53
    else:
        if alt6 >= 0.70:
            pred = OPP[nz[-1]]
            conf = 56
        elif alt6 <= 0.30:
            pred = nz[-1]
            conf = 54
        else:
            if perf['n'] > 10:
                if perf['alt'] > perf['fol'] + 1:
                    pred = OPP[nz[-1]]
                elif perf['fol'] > perf['alt'] + 1:
                    pred = nz[-1]
                else:
                    pred = OPP[nz[-1]]
            else:
                pred = OPP[nz[-1]]
            conf = 51
    
    ctx['last_pred'] = pred
    return pred, conf

def predict_F_dataaligned(history, ctx):
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 2: return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    if streak >= 3: return OPP[color], 55
    if streak == 2: return color, 54
    return OPP[nz[-1]], 51

# ─── NEW CANDIDATE G: Synthesized best approach ───
# Combines Phase 2 insights:
# - After pair: continue (52.9% observed)
# - After streak-3: fade (52.9% observed)  
# - After alternation: slight fade (51.6% observed break rate)
# - Adds: adaptive confidence from session's own pair/streak rates
# - Adds: streak-length awareness from running max streak

def predict_candidate_G(history, ctx):
    """Synthesized optimal: data-aligned + session-adaptive + streak-length awareness."""
    nz = [h for h in history if h != 'ZERO']
    if len(nz) < 3:
        return 'RED', 50
    
    streak, color = calc_current_streak(nz)
    
    # Track running max streak for this session
    max_streak = ctx.get('max_streak', 1)
    if streak > max_streak:
        max_streak = streak
        ctx['max_streak'] = max_streak
    
    # Track pair/streak empirical rates for this session
    stats = ctx.get('stats', {'pair_cont': 1, 'pair_break': 1, 's3_cont': 1, 's3_break': 1, 
                               'alt_same': 1, 'alt_diff': 1})
    
    # Update stats from the transition that just happened
    if len(nz) >= 3:
        prev_streak, prev_color = 1, nz[-2]
        for i in range(len(nz) - 3, -1, -1):
            if nz[i] == nz[-2]: prev_streak += 1
            else: break
        
        actual = nz[-1]
        
        if prev_streak == 2 and (len(nz) < 4 or nz[-4] != nz[-2]):
            # Was a pair
            if actual == prev_color:
                stats['pair_cont'] += 1
            else:
                stats['pair_break'] += 1
        elif prev_streak >= 3:
            if actual == prev_color:
                stats['s3_cont'] += 1
            else:
                stats['s3_break'] += 1
        elif prev_streak == 1:
            if actual == nz[-2]:
                stats['alt_same'] += 1
            else:
                stats['alt_diff'] += 1
    
    ctx['stats'] = stats
    
    # Decision logic
    if streak >= 3:
        # Session-adjusted fade confidence
        s3_break_rate = stats['s3_break'] / (stats['s3_cont'] + stats['s3_break'])
        
        # Dynamic threshold: if this session's streaks tend to be longer, hold off
        if streak < max_streak * 0.7 and s3_break_rate < 0.50:
            # This session has long streaks and they tend to continue
            return color, 52
        
        return OPP[color], int(50 + max(0, (s3_break_rate - 0.48)) * 60)
    
    if streak == 2:
        pair_cont_rate = stats['pair_cont'] / (stats['pair_cont'] + stats['pair_break'])
        if pair_cont_rate > 0.52:
            return color, int(50 + (pair_cont_rate - 0.5) * 40)
        elif pair_cont_rate < 0.48:
            return OPP[color], int(50 + (0.5 - pair_cont_rate) * 40)
        return color, 51  # Data says slight continue
    
    # Streak == 1 (alternation)
    alt_diff_rate = stats['alt_diff'] / (stats['alt_same'] + stats['alt_diff'])
    
    # Recent micro-context
    w8 = nz[-8:]
    alt8 = calc_alternation(w8)
    
    if alt8 >= 0.7:
        return OPP[nz[-1]], 55
    elif alt8 <= 0.3:
        return nz[-1], 54
    else:
        if alt_diff_rate > 0.52:
            return OPP[nz[-1]], 52
        elif alt_diff_rate < 0.48:
            return nz[-1], 52
        return OPP[nz[-1]], 51


def replay(outcomes, predict_fn):
    history = []
    ctx = {}
    wins = losses = 0
    max_cl = cl = 0
    
    for out in outcomes:
        if out == 'ZERO':
            history.append(out)
            continue
        pred, _ = predict_fn(history, ctx)
        if pred == out:
            wins += 1; cl = 0
        else:
            losses += 1; cl += 1
            max_cl = max(max_cl, cl)
        history.append(out)
    
    total = wins + losses
    return wins / total * 100 if total > 0 else 0, wins, losses, max_cl


def main():
    sessions = load_all_sessions()
    total_spins = sum(len(s['outcomes']) for s in sessions)
    total_nz = sum(sum(1 for o in s['outcomes'] if o != 'ZERO') for s in sessions)
    
    print(f"{'='*110}")
    print(f"  PHASE 4: COMPLETE COMBINED RESEARCH — {len(sessions)} sessions, {total_spins} total spins, {total_nz} bettable")
    print(f"{'='*110}\n")
    
    strategies = [
        ('CURRENT v15.1', predict_current_engine),
        ('B: Adaptive Regime', predict_B_adaptive),
        ('F: Data-Aligned', predict_F_dataaligned),
        ('G: Synthesized Optimal', predict_candidate_G),
    ]
    
    agg = {n: {'w':0,'l':0,'mcl':0,'wrs':[]} for n,_ in strategies}
    
    print(f"{'Session':<45}", end="")
    for n, _ in strategies:
        print(f" {n[:20]:>20}", end="")
    print()
    print("-" * 130)
    
    for sess in sessions:
        row = f"{sess['file']:<45}"
        for n, fn in strategies:
            wr, w, l, mcl = replay(sess['outcomes'], fn)
            agg[n]['w'] += w
            agg[n]['l'] += l
            agg[n]['mcl'] = max(agg[n]['mcl'], mcl)
            agg[n]['wrs'].append(wr)
            row += f" {wr:>19.1f}%"
        print(row)
    
    print(f"\n{'='*110}")
    print(f"  FINAL AGGREGATE (ALL {len(sessions)} sessions, {total_nz} non-zero bets)")
    print(f"{'='*110}\n")
    
    for n, a in sorted(agg.items(), key=lambda x: x[1]['w']/(x[1]['w']+x[1]['l']+1), reverse=True):
        total = a['w'] + a['l']
        wr = a['w'] / total * 100 if total > 0 else 0
        avg = sum(a['wrs'])/len(a['wrs']) if a['wrs'] else 0
        best = max(a['wrs']) if a['wrs'] else 0
        worst = min(a['wrs']) if a['wrs'] else 0
        median_wrs = sorted(a['wrs'])
        med = median_wrs[len(median_wrs)//2] if median_wrs else 0
        print(f"  {n:<25} WR: {wr:.2f}%  Avg: {avg:.1f}%  Med: {med:.1f}%  "
              f"Best: {best:.1f}%  Worst: {worst:.1f}%  MCL: {a['mcl']}")
    
    # Statistical significance
    print(f"\n{'='*110}")
    print(f"  STATISTICAL SIGNIFICANCE")
    print(f"{'='*110}\n")
    
    for n, a in sorted(agg.items(), key=lambda x: x[1]['w']/(x[1]['w']+x[1]['l']+1), reverse=True):
        total = a['w'] + a['l']
        p_hat = a['w'] / total
        se = math.sqrt(p_hat * (1 - p_hat) / total)
        z = (p_hat - 0.5) / se if se > 0 else 0
        print(f"  {n:<25}  p_hat={p_hat:.4f}  SE={se:.4f}  z={z:+.3f}  {'*' if abs(z) > 1.96 else '(not sig)'}")
    
    print(f"\n  Note: z > 1.96 means statistically significant above 50% at p < 0.05")
    print(f"        z > 2.576 means significant at p < 0.01")


if __name__ == '__main__':
    main()
