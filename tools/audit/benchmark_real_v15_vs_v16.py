import glob, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_0
from engine_mirror import PrngDetectorMirror

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

# Pure v15.2 implementation directly from commit 97b1e22
def predict_real_v15_2(history):
    raw = [h['outcome'] if isinstance(h, dict) else h for h in history]
    nonZero = [x for x in raw if x != 'ZERO']
    if len(nonZero) < 3:
        return (nonZero[-1] if nonZero else 'RED'), 50, 'АНАЛИЗ'
        
    color = nonZero[-1]
    oppColor = 'BLACK' if color == 'RED' else 'RED'
    
    streak = 1
    for k in range(len(nonZero)-2, -1, -1):
        if nonZero[k] == color: streak += 1
        else: break
        
    maxStreak = 1
    curStreak = 1
    for i in range(1, len(nonZero)):
        if nonZero[i] == nonZero[i-1]:
            curStreak += 1
            if curStreak > maxStreak: maxStreak = curStreak
        else:
            curStreak = 1
            
    pairCont = 1; pairBreak = 1
    s3Cont = 1; s3Break = 1
    altSame = 1; altDiff = 1
    
    for i in range(2, len(nonZero)):
        ps = 1
        pc = nonZero[i-1]
        for j in range(i-2, -1, -1):
            if nonZero[j] == pc: ps += 1
            else: break
        actual = nonZero[i]
        if ps == 2 and (i < 3 or nonZero[i-3] != pc):
            if actual == pc: pairCont += 1
            else: pairBreak += 1
        elif ps >= 3:
            if actual == pc: s3Cont += 1
            else: s3Break += 1
        elif ps == 1:
            if actual == nonZero[i-1]: altSame += 1
            else: altDiff += 1
            
    if streak >= 3:
        s3BreakRate = s3Break / (s3Cont + s3Break)
        if streak < maxStreak * 0.7 and s3BreakRate < 0.50:
            return color, 52, 'СЕРИЯ (ИМПУЛЬС)'
        conf = max(50, min(75, round(50 + max(0, s3BreakRate - 0.48) * 60)))
        return oppColor, conf, 'ОТСКОК ОТ ПОТОЛКА'
        
    if streak == 2:
        pairContRate = pairCont / (pairCont + pairBreak)
        if pairContRate > 0.52:
            conf = max(50, min(65, round(50 + (pairContRate - 0.5) * 40)))
            return color, conf, 'ПАРА (ПРОДОЛЖЕНИЕ)'
        elif pairContRate < 0.48:
            conf = max(50, min(65, round(50 + (0.5 - pairContRate) * 40)))
            return oppColor, conf, 'ПАРА (СЛОМ)'
        return color, 51, 'ПАРА (СТРАХОВКА)'
        
    # streak == 1
    altDiffRate = altDiff / (altSame + altDiff)
    w8 = nonZero[-8:]
    trans = sum(1 for i in range(1, len(w8)) if w8[i] != w8[i-1])
    alt8 = trans / max(1, len(w8)-1)
    
    if alt8 >= 0.7:
        return oppColor, 55, 'ЧЕРЕДОВАНИЕ (СЛОМ)'
    elif alt8 <= 0.3:
        return color, 54, 'ЧЕРЕДОВАНИЕ (ИМПУЛЬС)'
    else:
        if altDiffRate > 0.52:
            return oppColor, 52, 'ЧЕРЕДОВАНИЕ (СЛОМ-АДАПТИВ)'
        elif altDiffRate < 0.48:
            return color, 52, 'ЧЕРЕДОВАНИЕ (ПРОДОЛЖЕНИЕ-АДАПТИВ)'
        return oppColor, 51, 'ЧЕРЕДОВАНИЕ (БАЛАНС)'

def predict_v16_1(history):
    return PrngDetectorMirror.get_recommendation_and_confidence(history)

# Test all
models = [
    ('v15.0 FINAL APEX', lambda h: predict_v15_0([x['outcome'] for x in h])),
    ('v15.2 Synthesized Optimal', predict_real_v15_2),
    ('v16.1 APEX-Neural', predict_v16_1),
]

print("\n" + "="*95)
print(f"{'Engine Version':28s} | {'All 50 Sess WR':16s} | {'Bot Logs (15) WR':16s} | {'User Test (340) WR':16s}")
print("="*95)

for name, fn in models:
    t_spins, t_wins = 0, 0
    b_spins, b_wins = 0, 0
    u_spins, u_wins = 0, 0
    
    for s in sessions:
        outs = s['outcomes']
        hist = []
        is_bot = (s['source'] == 'bot_log')
        is_user = ('session_20261119_223110' in s['file'])
        
        for o in outs:
            res = fn(hist)
            rec = res if isinstance(res, str) else res[0]
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
            
    print(f"{name:28s} | {t_wins:4d}/{t_spins:4d} ({t_wins/t_spins*100:5.2f}%) | {b_wins:4d}/{b_spins:4d} ({b_wins/b_spins*100:5.2f}%) | {u_wins:3d}/{u_spins:3d} ({u_wins/u_spins*100:5.2f}%)")
print("="*95)
