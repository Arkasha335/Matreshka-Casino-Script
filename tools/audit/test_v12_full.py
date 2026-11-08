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

# v10.4 full mode detection
def calc_current_streak(non_zero):
    if len(non_zero) == 0: return 0
    s = 1
    last_col = non_zero[-1]['outcome']
    for i in range(len(non_zero)-2, -1, -1):
        if non_zero[i]['outcome'] == last_col: s += 1
        else: break
    return s

def calc_alternation(arr):
    if len(arr) < 3: return 0.5
    trans = sum(1 for i in range(1, len(arr)) if arr[i]['outcome'] != arr[i-1]['outcome'])
    return trans / (len(arr) - 1)

def count_streaks_gte(non_zero, min_len):
    if len(non_zero) == 0: return 0
    cnt = 0
    curr = 1
    last_col = non_zero[0]['outcome']
    for i in range(1, len(non_zero)):
        if non_zero[i]['outcome'] == last_col:
            curr += 1
        else:
            if curr >= min_len: cnt += 1
            curr = 1
            last_col = non_zero[i]['outcome']
    if curr >= min_len: cnt += 1
    return cnt

def detect_mode(history):
    non_zero = [h for h in history if h['outcome'] != 'ZERO']
    if len(non_zero) < 3: return 'ZEBRA'
    
    curr_streak = calc_current_streak(non_zero)
    fast_alt = calc_alternation(non_zero[-6:])
    slow_alt = calc_alternation(non_zero[-15:])
    streak3 = count_streaks_gte(non_zero[-15:], 3)
    zeros = sum(1 for h in history[-10:] if h['outcome'] == 'ZERO')
    
    score = 0
    if curr_streak >= 7: score -= 8
    elif curr_streak == 6: score -= 6
    elif curr_streak == 5: score -= 4
    elif curr_streak == 4: score -= 1
    elif curr_streak <= 2: score += 2
    
    if fast_alt >= 0.80: score += 3
    elif fast_alt >= 0.60: score += 1
    elif fast_alt < 0.30: score -= 2
    
    if slow_alt >= 0.70: score += 1
    elif slow_alt < 0.40: score -= 1
    
    if streak3 >= 3: score -= 2
    elif streak3 == 2: score -= 1
    elif streak3 == 0: score += 1
    
    if zeros >= 3: score -= 3
    elif zeros == 2: score -= 1
    
    if score >= 2: return 'ZEBRA'
    if score <= -2: return 'DANGER'
    return 'TRANSITION'

def detect_mode_with_hysteresis(history, prev_mode, curr_mode, spins_since_danger, spins_in_mode):
    raw_mode = detect_mode(history)
    z10 = sum(1 for h in history[-10:] if h['outcome'] == 'ZERO')
    eff_mode = 'TRANSITION' if (z10 >= 3 and raw_mode == 'ZEBRA') else raw_mode
    new_mode = eff_mode
    
    new_spins_since_danger = spins_since_danger + 1
    new_spins_in_mode = spins_in_mode + 1
    new_prev_mode = prev_mode
    
    if curr_mode == 'DANGER' and spins_in_mode < 3:
        new_mode = 'DANGER'
        
    if curr_mode == 'DANGER' and new_mode != 'DANGER' and spins_in_mode >= 3:
        new_mode = 'TRANSITION'
        new_spins_since_danger = 0
    elif new_spins_since_danger < 5 and new_mode == 'ZEBRA':
        new_mode = 'TRANSITION'
        
    if new_mode != curr_mode:
        new_prev_mode = curr_mode
        new_spins_in_mode = 1
        
    return new_mode, new_prev_mode, new_spins_since_danger, new_spins_in_mode

# Engine Params V12
def get_engine_params_v12(mode, bankroll):
    min_b = 500000.0
    max_b = 6500000.0
    clamped = max(min_b, min(bankroll, max_b))
    ratio = (clamped - min_b) / (max_b - min_b)
    
    # Base bet 1,500 to 4,000 for perfect 10-step margin
    full_base = round(1500.0 + ratio * (4000.0 - 1500.0))
    
    if mode == 'ZEBRA':
        # High profit mode on alternation!
        return {
            'baseBet': full_base,
            'step2Boost': 1.15,
            'step3Boost': 1.10
        }
    elif mode == 'TRANSITION':
        return {
            'baseBet': max(1000, round(full_base * 0.8)),
            'step2Boost': 1.10,
            'step3Boost': 1.05
        }
    else: # DANGER
        return {
            'baseBet': max(1000, round(full_base * 0.6)),
            'step2Boost': 1.0,
            'step3Boost': 1.0 # Pure TBB only!
        }

def get_apex_matrix(history, window=20):
    non_zero = [h for h in history if h['outcome'] != 'ZERO'][-window:]
    red_count = sum(1 for h in non_zero if h['outcome'] == 'RED')
    black_count = sum(1 for h in non_zero if h['outcome'] == 'BLACK')
    max_streak_red = 0
    max_streak_black = 0
    curr_streak = 0
    curr_color = None
    for h in non_zero:
        if h['outcome'] == curr_color: curr_streak += 1
        else: curr_color = h['outcome']; curr_streak = 1
        if curr_color == 'RED' and curr_streak > max_streak_red: max_streak_red = curr_streak
        if curr_color == 'BLACK' and curr_streak > max_streak_black: max_streak_black = curr_streak
    alpha = 'NEUTRAL'
    omega = 'NEUTRAL'
    if len(non_zero) > 0:
        if red_count / len(non_zero) > 0.55: alpha = 'RED'; omega = 'BLACK'
        elif black_count / len(non_zero) > 0.55: alpha = 'BLACK'; omega = 'RED'
    curr_active_streak = 0
    curr_active_color = None
    if len(non_zero) > 0:
        curr_active_color = non_zero[-1]['outcome']
        for i in range(len(non_zero)-1, -1, -1):
            if non_zero[i]['outcome'] == curr_active_color: curr_active_streak += 1
            else: break
    return {
        'alpha': alpha, 'omega': omega, 'maxStreakRed': max_streak_red,
        'maxStreakBlack': max_streak_black, 'currentActiveColor': curr_active_color,
        'currentActiveStreak': curr_active_streak
    }

def get_zebra_momentum(history):
    non_zero = [h for h in history if h['outcome'] != 'ZERO'][-6:]
    if len(non_zero) < 4: return True, 55
    alt = sum(1 for i in range(1, len(non_zero)) if non_zero[i]['outcome'] != non_zero[i-1]['outcome'])
    alt_rate = alt / max(1, len(non_zero) - 1)
    if alt_rate >= 0.80: return False, 65
    elif alt_rate >= 0.60: return True, 55
    else: return True, 58

def get_recommendation_and_confidence(history):
    if len(history) == 0: return 'RED', 50, 'АНАЛИЗ'
    matrix = get_apex_matrix(history)
    non_zero = [h for h in history if h['outcome'] != 'ZERO']
    if len(non_zero) >= 4:
        L1 = non_zero[-1]['outcome']; L2 = non_zero[-2]['outcome']; L3 = non_zero[-3]['outcome']; L4 = non_zero[-4]['outcome']
        if L1 == L3 and L2 == L4 and L1 != L2: return ('BLACK' if L1 == 'RED' else 'RED'), 82, 'ЭХО-ПАТТЕРН'
        if L1 == L2 and L2 == L3 and L4 != L1: return ('BLACK' if L1 == 'RED' else 'RED'), 78, 'ВОЛНА (СЛОМ СЕРИИ)'
    if len(non_zero) < 2: return (non_zero[-1]['outcome'] if len(non_zero) > 0 else 'RED'), 50, 'АНАЛИЗ'
    L1 = non_zero[-1]['outcome']; L2 = non_zero[-2]['outcome']
    curr_max = matrix['maxStreakRed'] if matrix['currentActiveColor'] == 'RED' else matrix['maxStreakBlack']
    if matrix['currentActiveColor'] and matrix['currentActiveStreak'] >= curr_max and curr_max > 0:
        return ('BLACK' if matrix['currentActiveColor'] == 'RED' else 'RED'), 90, 'ОТСКОК ОТ ПОТОЛКА'
    elif L1 == L2:
        if L1 == matrix['alpha'] and curr_max > 2: return L1, 75, 'АЛЬФА-ТРЕНД'
        elif L1 == matrix['omega']: return ('BLACK' if L1 == 'RED' else 'RED'), 30, 'ОМЕГА-ЛОВУШКА'
        else: return ('BLACK' if L1 == 'RED' else 'RED'), 50, 'НЕЙТРАЛЬНО'
    else:
        follow_l1, conf = get_zebra_momentum(history)
        rec = L1 if follow_l1 else ('BLACK' if L1 == 'RED' else 'RED')
        return rec, conf, ('ЧЕРЕДОВАНИЕ (FOLLOW)' if follow_l1 else 'ЧЕРЕДОВАНИЕ (BREAK)')

def run_v12_full(outcomes, initial_b):
    bal = float(initial_b)
    peak = bal
    max_dd = 0.0
    cdt = 0.0
    step = 1
    history = []
    wins = 0
    losses = 0
    limit_hits = 0
    
    curr_mode = 'ZEBRA'
    prev_mode = 'ZEBRA'
    spins_since_danger = 999
    spins_in_mode = 0
    
    for out in outcomes:
        params = get_engine_params_v12(curr_mode, bal)
        rec, conf, pat = get_recommendation_and_confidence(history)
        
        # Bet Calculation
        if cdt <= 0:
            bet = params['baseBet']
        else:
            tbb = round((cdt + params['baseBet']) / 0.98)
            if step == 2 and params['step2Boost'] > 1.0:
                bet = round(tbb * params['step2Boost'])
            elif step == 3 and params['step3Boost'] > 1.0:
                bet = round(tbb * params['step3Boost'])
            else:
                bet = tbb
                
        if bet >= 1000000.0:
            bet = 1000000.0
            limit_hits += 1
            
        if bet > bal:
            bet = bal
            
        is_win = (out == rec and out != 'ZERO')
        if out == 'ZERO':
            losses += 1
            bal -= bet
            cdt += bet
            # Zero increments step
            step += 1
        elif is_win:
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
            
        if bal > peak: peak = bal
        dd = peak - bal
        if dd > max_dd: max_dd = dd
        
        entry = {'outcome': out, 'betAmount': bet, 'betColor': rec, 'isWin': is_win}
        history.append(entry)
        
        # Mode update with hysteresis
        curr_mode, prev_mode, spins_since_danger, spins_in_mode = detect_mode_with_hysteresis(
            history, prev_mode, curr_mode, spins_since_danger, spins_in_mode
        )
        
        if bal <= 0: break
        
    return {
        "profit": bal - initial_b,
        "max_dd_pct": (max_dd / initial_b) * 100.0 if initial_b > 0 else 0,
        "wins": wins,
        "winrate": (wins / len(outcomes) * 100.0) if outcomes else 0,
        "limit_hits": limit_hits
    }

print("=== BENCHMARK V12 FULL WITH ADAPTIVE SERVER MODES ===")
print(f"{'Session Name':<40} | {'Initial (₽)':<12} | {'Profit V12':<14} | {'MaxDD (%)':<10} | {'Winrate':<8} | {'Status'}")
print("-" * 98)

total_p = 0
for sname, sdata in sessions.items():
    res = run_v12_full(sdata["outcomes"], sdata["initial"])
    total_p += res["profit"]
    status = f"Limit x{res['limit_hits']}" if res['limit_hits'] > 0 else "PERFECT"
    print(f"{sname:<40} | {sdata['initial']:>12,.0f} | {res['profit']:>14,.0f} | {res['max_dd_pct']:>8.1f}% | {res['winrate']:>6.1f}% | {status}")

print("-" * 98)
print(f"TOTAL V12 FULL PROFIT: {total_p:,.2f} RUB")
