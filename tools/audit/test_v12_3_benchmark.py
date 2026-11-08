import glob
import json
import math
import os

files = sorted(glob.glob(r'd:\Downloads\matreshka*.json'))

def load_session(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    outcomes = []
    initial = 2000000
    if 'metadata' in data:
        initial = data['metadata'].get('initialBankroll', 2000000)
    if 'history' in data:
        for h in data['history']:
            outcomes.append(h['outcome'])
    elif 'logs' in data:
        for l in data['logs']:
            outcomes.append(l['input_result'])
    return outcomes, initial

def detect_mode_fast(history):
    """
    Fast and responsive 3-mode detection:
    - ZEBRA: clean alternation, streaks <= 2, zero absent in last 5.
    - TRANSITION ("Жёлтенький"): 3-4 of same color, moderate alt, 1 recent zero.
    - DANGER: streaks >= 5, or >= 2 zeros in last 10, or streak >= 4 with low alt.
    """
    if len(history) < 3:
        return 'ZEBRA'
    
    non_zero = [h for h in history if h != 'ZERO']
    if len(non_zero) < 3:
        return 'ZEBRA'
    
    # Current active streak
    curr_streak = 1
    last_col = non_zero[-1]
    for i in range(len(non_zero) - 2, -1, -1):
        if non_zero[i] == last_col:
            curr_streak += 1
        else:
            break
            
    # Alternation in last 6 and last 12
    recent_nz = non_zero[-6:]
    alt_count = sum(1 for i in range(1, len(recent_nz)) if recent_nz[i] != recent_nz[i-1])
    fast_alt = alt_count / max(1, len(recent_nz) - 1)
    
    zero_count_10 = history[-10:].count('ZERO')
    zero_count_5 = history[-5:].count('ZERO')
    
    # 1. DANGER Triggers (Immediate)
    if curr_streak >= 5:
        return 'DANGER'
    if zero_count_10 >= 2:
        return 'DANGER'
    if curr_streak >= 4 and fast_alt <= 0.25:
        return 'DANGER'
        
    # 2. TRANSITION Triggers ("Жёлтенький")
    if curr_streak >= 3:
        return 'TRANSITION'
    if zero_count_5 >= 1:
        return 'TRANSITION'
    if fast_alt < 0.60:
        return 'TRANSITION'
        
    # 3. ZEBRA Triggers
    if curr_streak <= 2 and fast_alt >= 0.60 and zero_count_5 == 0:
        return 'ZEBRA'
        
    return 'TRANSITION'

def predict_color(history, mode):
    """
    Color recommendation with MPD and mode adaptation.
    """
    non_zero = [h for h in history if h != 'ZERO']
    if len(non_zero) == 0:
        return 'RED'
    if len(non_zero) == 1:
        return 'BLACK' if non_zero[-1] == 'RED' else 'RED'
        
    L1 = non_zero[-1]
    L2 = non_zero[-2]
    
    # Micro-pattern: A-B-A-B echo
    if len(non_zero) >= 4:
        L3 = non_zero[-3]
        L4 = non_zero[-4]
        if L1 == L3 and L2 == L4 and L1 != L2:
            return 'BLACK' if L1 == 'RED' else 'RED'
        # 3-in-a-row break wave
        if L1 == L2 and L2 == L3 and L4 != L1:
            return 'BLACK' if L1 == 'RED' else 'RED'
            
    # Current active streak
    curr_streak = 1
    for i in range(len(non_zero) - 2, -1, -1):
        if non_zero[i] == L1:
            curr_streak += 1
        else:
            break
            
    if mode == 'ZEBRA':
        # Alternation mode: predict opposite of L1 unless L1 == L2
        if L1 != L2:
            return 'BLACK' if L1 == 'RED' else 'RED'
        else:
            return 'BLACK' if L1 == 'RED' else 'RED'
            
    elif mode == 'TRANSITION':
        # Moderate mode: streaks of 3-4
        if curr_streak >= 3:
            # Expect break
            return 'BLACK' if L1 == 'RED' else 'RED'
        else:
            return 'BLACK' if L1 == 'RED' else 'RED'
            
    else: # DANGER
        # Extreme series: if streak >= 6, ceiling bounce; if 4-5, follow Alpha trend
        if curr_streak >= 6:
            return 'BLACK' if L1 == 'RED' else 'RED'
        elif curr_streak in (4, 5):
            return L1  # Ride trend
        else:
            return 'BLACK' if L1 == 'RED' else 'RED'

def get_engine_bet(step, cdt, mode, bankroll, profile='APEX'):
    """
    Geometric constant multiplier progression.
    Table limits: min 1,000, max 1,000,000 RUB.
    Target steps = 10 steps to 1,000,000 RUB.
    """
    MIN_BET = 1000
    MAX_BET = 1000000
    
    # Base bet per mode
    if mode == 'ZEBRA':
        base_b0 = 1200 if (bankroll >= 1900000 and profile == 'APEX') else 1000
    elif mode == 'TRANSITION':
        base_b0 = 1000
    else: # DANGER
        base_b0 = 1000
        
    base_b0 = max(MIN_BET, min(base_b0, bankroll))
    
    if step <= 1 or cdt <= 0:
        return base_b0
        
    target_steps = 10
    terminal_cap = min(MAX_BET, math.floor(bankroll / 1.90))
    terminal_cap = max(MIN_BET, terminal_cap)
    
    # Constant multiplier X
    ratio = terminal_cap / max(1, base_b0)
    exponent = 1.0 / max(1, target_steps - 1)
    X = max(2.025, min(2.40, math.pow(ratio, exponent)))
    
    # Remaining steps
    remaining = max(1, target_steps - step + 1)
    if remaining == 1:
        return min(terminal_cap, bankroll)
        
    prev_bet = max(base_b0, round(base_b0 * math.pow(X, step - 2)))
    step_ratio = terminal_cap / max(1, prev_bet)
    step_X = max(2.025, min(2.40, math.pow(step_ratio, 1.0 / remaining)))
    geom_bet = round(prev_bet * step_X)
    
    # Strict debt coverage under 2% tax
    min_tbb = math.ceil((cdt + base_b0) / 0.98)
    bet = max(min_tbb, geom_bet)
    
    # Hard bounds
    final_bet = max(MIN_BET, min(bet, MAX_BET, bankroll))
    return int(round(final_bet))

def run_simulation(outcomes, initial_b, profile='APEX'):
    bankroll = int(initial_b)
    peak = bankroll
    max_dd = 0
    cdt = 0
    step = 1
    wins = 0
    losses = 0
    history = []
    mode_counts = {'ZEBRA': 0, 'TRANSITION': 0, 'DANGER': 0}
    
    for outcome in outcomes:
        mode = detect_mode_fast(history)
        mode_counts[mode] += 1
        
        bet = get_engine_bet(step, cdt, mode, bankroll, profile)
        color = predict_color(history, mode)
        
        is_win = (outcome == color)
        
        if is_win:
            net_profit = int(round(bet * 0.98))
            bankroll += net_profit
            cdt = 0
            step = 1
            wins += 1
        else:
            net_profit = -bet
            bankroll += net_profit
            cdt += bet
            step += 1
            losses += 1
            
        history.append(outcome)
        
        if bankroll > peak:
            peak = bankroll
        dd = peak - bankroll
        if dd > max_dd:
            max_dd = dd
            
        if bankroll < 1000:
            break
            
    net_total = bankroll - int(initial_b)
    return {
        'net_total': net_total,
        'max_dd': max_dd,
        'final_bankroll': bankroll,
        'is_ruined': bankroll < 1000,
        'spins': len(outcomes),
        'wins': wins,
        'losses': losses,
        'mode_counts': mode_counts
    }

print("Running benchmark on all 16 sessions...")
results = []
for f in files:
    outcomes, initial = load_session(f)
    res = run_simulation(outcomes, initial, profile='APEX')
    fname = os.path.basename(f)
    results.append((fname, res))
    print(f"{fname[:32]:<32} | Spins: {res['spins']:3d} | Profit: {res['net_total']:+10d} RUB | MaxDD: {res['max_dd']:8d} RUB | Modes: Z:{res['mode_counts']['ZEBRA']} T:{res['mode_counts']['TRANSITION']} D:{res['mode_counts']['DANGER']}")

total_profit = sum(r[1]['net_total'] for r in results)
won_sessions = sum(1 for r in results if r[1]['net_total'] > 0)
max_overall_dd = max(r[1]['max_dd'] for r in results)
print("=" * 80)
print(f"TOTAL PROFIT: {total_profit:+d} RUB")
print(f"WON SESSIONS: {won_sessions} / {len(results)} ({won_sessions/len(results)*100:.1f}%)")
print(f"MAX DRAWDOWN: {max_overall_dd:d} RUB")
