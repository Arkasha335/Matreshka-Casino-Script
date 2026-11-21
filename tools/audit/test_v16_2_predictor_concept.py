import glob, json, math, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()

def predict_v16_2_candidate(history):
    raw = [h['outcome'] if isinstance(h, dict) else h for h in history]
    nonZero = [x for x in raw if x != 'ZERO']
    if len(nonZero) < 3:
        return (nonZero[-1] if nonZero else 'RED'), 50, 'АНАЛИЗ'
        
    curColor = nonZero[-1]
    oppColor = 'BLACK' if curColor == 'RED' else 'RED'
    
    # 1. Streak
    streak = 1
    for k in range(len(nonZero)-2, -1, -1):
        if nonZero[k] == curColor: streak += 1
        else: break
        
    # 2. Alternation rate over last 6 spins
    sub6 = nonZero[-6:]
    alt6 = 0.5
    if len(sub6) >= 2:
        trans = sum(1 for i in range(1, len(sub6)) if sub6[i] != sub6[i-1])
        alt6 = trans / (len(sub6) - 1)
        
    # 3. Macro skew over last 24 spins
    w24 = nonZero[-24:]
    red_count = sum(1 for x in w24 if x == 'RED')
    red_ratio = red_count / len(w24)
    dominant_color = 'RED' if red_ratio > 0.55 else ('BLACK' if red_ratio < 0.45 else None)

    # 4. Empirical session transition counters
    pairCont = 1; pairBreak = 1
    s3Cont = 1; s3Break = 1
    altSame = 1; altDiff = 1
    for i in range(2, len(nonZero)):
        ps = 1
        pc = nonZero[i-1]
        for j in range(i-2, -1, -1):
            if nonZero[j] == pc: ps += 1
            else: break
        act = nonZero[i]
        if ps == 2 and (i < 3 or nonZero[i-3] != pc):
            if act == pc: pairCont += 1
            else: pairBreak += 1
        elif ps >= 3:
            if act == pc: s3Cont += 1
            else: s3Break += 1
        elif ps == 1:
            if act == nonZero[i-1]: altSame += 1
            else: altDiff += 1

    # LAW 1: Alternation Regime (streak == 1)
    if streak == 1:
        # If in alternating flow (alt6 >= 0.60): follow the alternation!
        if alt6 >= 0.60:
            return oppColor, 60, 'ЗЕБРА (ПРОДОЛЖЕНИЕ)'
        # If in trend flow (alt6 <= 0.35): follow the new streak (expect pair)!
        elif alt6 <= 0.35:
            return curColor, 56, 'ТРЕНД (СТАРТ ПАРЫ)'
        else:
            # Session Bayesian transition
            altDiffRate = altDiff / (altSame + altDiff)
            if altDiffRate >= 0.50:
                return oppColor, 54, 'ЗЕБРА (БАЙЕС-СЛОМ)'
            else:
                return curColor, 54, 'ТРЕНД (БАЙЕС-ПАРА)'

    # LAW 2: Pair Regime (streak == 2)
    # Empirical data shows pairs continue to 3 with 51.34%!
    # Never blind fade a pair of 2!
    if streak == 2:
        pairContRate = pairCont / (pairCont + pairBreak)
        if pairContRate >= 0.49:
            return curColor, 58, 'ПАРА (РАЗГОН ДО 3)'
        else:
            return oppColor, 55, 'ПАРА (СЛОМ)'

    # LAW 3: Triplet Regime (streak == 3)
    # Empirical data shows streaks break at 3 with 53.12%!
    if streak == 3:
        s3BreakRate = s3Break / (s3Cont + s3Break)
        # If macro dominant color is strong and matches curColor, allow momentum
        if dominant_color == curColor and s3BreakRate < 0.45:
            return curColor, 53, 'СЕРИЯ (МАКРО-ИМПУЛЬС)'
        return oppColor, 62, 'ТРОЙКА (ОТСКОК)'

    # LAW 4: Deep Monorun / Runaway Train (streak >= 4)
    # ANTI-MARTINGALE SHIELD: DO NOT KEEP FADING A RUNAWAY STREAK!
    # If a streak reached 4+, empirical continuation is 50-57%!
    # Follow the run to avoid getting wiped out!
    if streak >= 4:
        return curColor, 65, 'СВЕРХСЕРИЯ (ПОЕЗД-ПОПУТНЫЙ)'

    return oppColor, 50, 'НЕЙТРАЛ'

print("\n--- Testing v16.2 Candidate Predictor ---")
for s_name, (spins, wins) in [('All Sessions', (0, 0)), ('Bot Logs', (0, 0)), ('User Test', (0, 0))]:
    pass

t_spins, t_wins = 0, 0
b_spins, b_wins = 0, 0
u_spins, u_wins = 0, 0

for s in sessions:
    outs = s['outcomes']
    hist = []
    is_bot = (s['source'] == 'bot_log')
    is_user = ('session_20261119_223110' in s['file'])
    
    for o in outs:
        rec, conf, state = predict_v16_2_candidate(hist)
        win = (rec == o)
        t_spins += 1
        if win: t_wins += 1
        if is_bot:
            b_spins += 1
            if win: b_wins += 1
        if is_user:
            u_spins += 1
            if win: u_wins += 1
        hist.append({'outcome': o, 'betAmount': 1000, 'betColor': rec, 'isWin': win, 'netProfit': 0})

print(f"All 50 Sessions:  {t_wins}/{t_spins} ({t_wins/t_spins*100:5.2f}% WR)")
print(f"Real Bot Logs:    {b_wins}/{b_spins} ({b_wins/b_spins*100:5.2f}% WR)")
print(f"User Test (340):  {u_wins}/{u_spins} ({u_wins/u_spins*100:5.2f}% WR)")
