import json
import glob
import os
import math
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Load all 13 sessions
log_dir = r"D:\Vibe\matreshka-quantum\log storage"
all_files = sorted(glob.glob(os.path.join(log_dir, "*.json")))
all_files.append(r"d:\Downloads\matreshka_quantum_v11_2026-11-08.json")

sessions = {}
for fpath in all_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    logs = data.get("logs", [])
    if logs:
        init_b = data.get("metadata", {}).get("initialBankroll") or logs[0].get("current_balance") or 1000000
        sessions[fname] = {
            "initial": init_b,
            "outcomes": [l["input_result"] for l in logs]
        }

# Exact v10.4 prediction engine
def get_apex_matrix(history, window=20):
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
        if curr_color == 'RED' and curr_streak > max_streak_red: max_streak_red = curr_streak
        if curr_color == 'BLACK' and curr_streak > max_streak_black: max_streak_black = curr_streak
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

def get_zebra_momentum(history):
    non_zero = [h for h in history if h['outcome'] != 'ZERO'][-6:]
    if len(non_zero) < 4:
        return True, 55
    alt = sum(1 for i in range(1, len(non_zero)) if non_zero[i]['outcome'] != non_zero[i-1]['outcome'])
    alt_rate = alt / max(1, len(non_zero) - 1)
    if alt_rate >= 0.80:
        return False, 65
    elif alt_rate >= 0.60:
        return True, 55
    else:
        return True, 58

def get_recommendation_and_confidence(history):
    if len(history) == 0:
        return 'RED', 50, 'АНАЛИЗ'
    matrix = get_apex_matrix(history)
    non_zero = [h for h in history if h['outcome'] != 'ZERO']
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
    curr_max = matrix['maxStreakRed'] if matrix['currentActiveColor'] == 'RED' else matrix['maxStreakBlack']
    if matrix['currentActiveColor'] and matrix['currentActiveStreak'] >= curr_max and curr_max > 0:
        return ('BLACK' if matrix['currentActiveColor'] == 'RED' else 'RED'), 90, 'ОТСКОК ОТ ПОТОЛКА'
    elif L1 == L2:
        if L1 == matrix['alpha'] and curr_max > 2:
            return L1, 75, 'АЛЬФА-ТРЕНД'
        elif L1 == matrix['omega']:
            return ('BLACK' if L1 == 'RED' else 'RED'), 30, 'ОМЕГА-ЛОВУШКА'
        else:
            return ('BLACK' if L1 == 'RED' else 'RED'), 50, 'НЕЙТРАЛЬНО'
    else:
        follow_l1, conf = get_zebra_momentum(history)
        rec = L1 if follow_l1 else ('BLACK' if L1 == 'RED' else 'RED')
        return rec, conf, ('ЧЕРЕДОВАНИЕ (FOLLOW)' if follow_l1 else 'ЧЕРЕДОВАНИЕ (BREAK)')

# V12 Proposed Engine
def run_v12_engine(outcomes, initial_b):
    bal = float(initial_b)
    peak = bal
    max_dd = 0.0
    cdt = 0.0
    step = 1
    history = []
    wins = 0
    losses = 0
    limit_hits = 0
    
    # 1. Base Bet Scaler: 1,500 to 4,500 based on bankroll (Guarantees 10 steps to 1M)
    min_b = 500000.0
    max_b = 6500000.0
    clamped = max(min_b, min(bal, max_b))
    ratio = (clamped - min_b) / (max_b - min_b)
    base_bet = round(1500.0 + ratio * (4500.0 - 1500.0))
    
    for out in outcomes:
        rec, conf, pat = get_recommendation_and_confidence(history)
        
        # 2. V12 Bet Calculation
        if cdt <= 0:
            bet = base_bet
        else:
            tbb = round((cdt + base_bet) / 0.98)
            # Tiered Smart Multiplier:
            # Step 2: 1.15x boost for higher profit
            # Step 3: 1.10x boost
            # Step 4+: Pure TBB to ensure up to 10 full steps before 1M!
            if step == 2:
                bet = max(round(tbb * 1.15), round(base_bet * 2.15))
            elif step == 3:
                bet = max(round(tbb * 1.10), round(base_bet * (2.15 ** 2)))
            else:
                bet = tbb
                
        if bet >= 1000000.0:
            bet = 1000000.0
            limit_hits += 1
            
        if bet > bal:
            bet = bal
            
        # 3. Outcome Processing
        if out == 'ZERO':
            losses += 1
            bal -= bet
            cdt += bet
            # Zero increments step
            step += 1
        elif out == rec:
            wins += 1
            pnl = bet * 0.98
            bal += pnl
            cdt = max(0.0, cdt - pnl)
            if cdt < 10.0:
                cdt = 0.0
                step = 1
        else:
            losses += 1
            bal -= bet
            cdt += bet
            step += 1
            
        if bal > peak:
            peak = bal
        dd = peak - bal
        if dd > max_dd:
            max_dd = dd
            
        history.append({'outcome': out, 'betAmount': bet, 'betColor': rec, 'isWin': (out == rec and out != 'ZERO')})
        if bal <= 0:
            break
            
    return {
        "final_profit": bal - initial_b,
        "max_dd": max_dd,
        "max_dd_pct": (max_dd / initial_b) * 100.0 if initial_b > 0 else 0,
        "wins": wins,
        "losses": losses,
        "winrate": (wins / len(outcomes) * 100.0) if outcomes else 0,
        "limit_hits": limit_hits,
        "ruined": bal <= 0
    }

print("=== BENCHMARK: V12 QUANTUM APEX ACROSS ALL 13 SESSIONS ===")
print(f"{'Session Name':<40} | {'Initial (₽)':<12} | {'Profit V12':<14} | {'MaxDD (%)':<10} | {'Winrate':<8} | {'Status'}")
print("-" * 98)

tot_profit = 0
for sname, sdata in sessions.items():
    res = run_v12_engine(sdata["outcomes"], sdata["initial"])
    tot_profit += res["final_profit"]
    status = "RUINED" if res["ruined"] else f"Limit x{res['limit_hits']}" if res['limit_hits'] > 0 else "PERFECT"
    print(f"{sname:<40} | {sdata['initial']:>12,.0f} | {res['final_profit']:>14,.0f} | {res['max_dd_pct']:>8.1f}% | {res['winrate']:>6.1f}% | {status}")

print("-" * 98)
print(f"TOTAL V12 PROFIT: {tot_profit:,.2f} RUB")
