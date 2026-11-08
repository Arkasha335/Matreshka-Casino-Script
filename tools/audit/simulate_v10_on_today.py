import json
import math
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Implement exact v10.4 logic from page.tsx (lines 100-520)
def get_apex_matrix_v10(history, window=20):
    non_zero = [h for h in history if h['outcome'] != 'ZERO'][-window:]
    red_count = sum(1 for h in non_zero if h['outcome'] == 'RED')
    black_count = sum(1 for h in non_zero if h['outcome'] == 'BLACK')
    
    max_streak_red = 0
    max_streak_black = 0
    curr_streak = 0
    curr_color = None
    
    for h in non_zero:
        if h['outcome'] == curr_color:
            curr_streak += 1
        else:
            curr_color = h['outcome']
            curr_streak = 1
        if curr_color == 'RED' and curr_streak > max_streak_red:
            max_streak_red = curr_streak
        if curr_color == 'BLACK' and curr_streak > max_streak_black:
            max_streak_black = curr_streak
            
    alpha = 'NEUTRAL'
    omega = 'NEUTRAL'
    if len(non_zero) > 0:
        if red_count / len(non_zero) > 0.55:
            alpha = 'RED'
            omega = 'BLACK'
        elif black_count / len(non_zero) > 0.55:
            alpha = 'BLACK'
            omega = 'RED'
            
    curr_active_streak = 0
    curr_active_color = None
    if len(non_zero) > 0:
        curr_active_color = non_zero[-1]['outcome']
        for i in range(len(non_zero)-1, -1, -1):
            if non_zero[i]['outcome'] == curr_active_color:
                curr_active_streak += 1
            else:
                break
                
    return {
        'alpha': alpha,
        'omega': omega,
        'maxStreakRed': max_streak_red,
        'maxStreakBlack': max_streak_black,
        'currentActiveColor': curr_active_color,
        'currentActiveStreak': curr_active_streak
    }

def get_zebra_momentum_v10(history):
    non_zero = [h for h in history if h['outcome'] != 'ZERO'][-6:]
    if len(non_zero) < 4:
        return True, 55
    alt = sum(1 for i in range(1, len(non_zero)) if non_zero[i]['outcome'] != non_zero[i-1]['outcome'])
    alt_rate = alt / (len(non_zero) - 1)
    if alt_rate >= 0.80:
        return False, 65
    elif alt_rate >= 0.60:
        return True, 55
    else:
        return True, 58

def get_recommendation_v10(history):
    if len(history) == 0:
        return 'RED', 50, 'АНАЛИЗ'
        
    matrix = get_apex_matrix_v10(history)
    non_zero = [h for h in history if h['outcome'] != 'ZERO']
    
    # MPD
    if len(non_zero) >= 4:
        L1 = non_zero[-1]['outcome']
        L2 = non_zero[-2]['outcome']
        L3 = non_zero[-3]['outcome']
        L4 = non_zero[-4]['outcome']
        
        if L1 == L3 and L2 == L4 and L1 != L2:
            return ('BLACK' if L1 == 'RED' else 'RED'), 82, 'ЭХО-ПАТТЕРН'
            
        if L1 == L2 and L2 == L3 and L4 != L1:
            return ('BLACK' if L1 == 'RED' else 'RED'), 78, 'ВОЛНА (СЛОМ СЕРИИ)'
            
    if len(non_zero) < 2:
        return (non_zero[-1]['outcome'] if len(non_zero) > 0 else 'RED'), 50, 'АНАЛИЗ'
        
    L1 = non_zero[-1]['outcome']
    L2 = non_zero[-2]['outcome']
    curr_max_streak = matrix['maxStreakRed'] if matrix['currentActiveColor'] == 'RED' else matrix['maxStreakBlack']
    
    if matrix['currentActiveColor'] and matrix['currentActiveStreak'] >= curr_max_streak and curr_max_streak > 0:
        return ('BLACK' if matrix['currentActiveColor'] == 'RED' else 'RED'), 90, 'ОТСКОК ОТ ПОТОЛКА'
    elif L1 == L2:
        if L1 == matrix['alpha'] and curr_max_streak > 2:
            return L1, 75, 'АЛЬФА-ТРЕНД'
        elif L1 == matrix['omega']:
            return ('BLACK' if L1 == 'RED' else 'RED'), 30, 'ОМЕГА-ЛОВУШКА'
        else:
            return ('BLACK' if L1 == 'RED' else 'RED'), 50, 'НЕЙТРАЛЬНО'
    else:
        follow_l1, conf = get_zebra_momentum_v10(history)
        rec = L1 if follow_l1 else ('BLACK' if L1 == 'RED' else 'RED')
        return rec, conf, ('ЧЕРЕДОВАНИЕ (FOLLOW)' if follow_l1 else 'ЧЕРЕДОВАНИЕ (BREAK)')

def calc_bet_v10(cdt, step, bankroll):
    min_b = 500000
    max_b = 6500000
    clamped = max(min_b, min(bankroll, max_b))
    ratio = (clamped - min_b) / (max_b - min_b)
    
    base_bet = 1000 + ratio * (4000 - 1000)
    growth = 2.2 + ratio * (2.5 - 2.2)
    sniper_mult = 1.6
    
    if cdt <= 0:
        return round(base_bet)
        
    tbb = round((cdt + base_bet) / 0.98)
    geom = round(base_bet * (growth ** (step - 1)))
    
    if cdt > base_bet * 2 and step >= 2:
        sniper_bet = round(tbb * sniper_mult)
        bet = max(sniper_bet, geom)
    else:
        bet = max(tbb, geom)
        
    return max(base_bet, min(bet, 1000000, bankroll))

with open(r"d:\Downloads\matreshka_quantum_v11_2026-11-08.json", "r", encoding="utf-8") as f:
    data = json.load(f)

logs = data.get("logs", [])
outcomes = [l["input_result"] for l in logs]
initial_b = data.get("metadata", {}).get("initialBankroll", 4369104)

print("=== SIMULATING EXACT V10.4 LOGIC ON TODAY'S 36 SPINS ===")
bal = initial_b
cdt = 0
step = 1
history = []
wins = 0
losses = 0

print(f"{'#':<3} | {'Outcome':<7} | {'Rec v10':<7} | {'Bet v10':<10} | {'Step':<5} | {'Profit':<10} | {'Win':<5} | {'Pattern v10'}")
print("-" * 80)

for i, out in enumerate(outcomes):
    rec, conf, pat = get_recommendation_v10(history)
    bet = calc_bet_v10(cdt, step, bal)
    
    is_win = (out == rec and out != 'ZERO')
    if is_win:
        wins += 1
        pnl = bet * 0.98
        bal += pnl
        cdt = max(0, cdt - pnl)
        if cdt < 10:
            cdt = 0
            step = 1
    else:
        losses += 1
        pnl = -bet
        bal += pnl
        cdt += bet
        step += 1
        
    history.append({'outcome': out, 'betAmount': bet, 'betColor': rec, 'isWin': is_win, 'netProfit': pnl})
    print(f"{i+1:<3} | {out:<7} | {rec:<7} | {bet:>10,d} | {step:<5} | {pnl:>10,.0f} | {str(is_win):<5} | {pat}")

print("-" * 80)
print(f"v10.4 Final Profit: {bal - initial_b:,.2f} RUB")
print(f"v10.4 Wins: {wins}, Losses: {losses}, Winrate: {wins/len(outcomes)*100:.1f}%")
