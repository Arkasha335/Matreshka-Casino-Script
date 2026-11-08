import os, sys, math, json, glob

sys.path.append(os.path.dirname(__file__))
from simulate_terminal_strategies import MPDPredictor

def get_calibrated_base_bet(profile, mode, bankroll):
    b = max(100_000, bankroll)
    if profile == 'TURBO_HARVEST':
        if b >= 3_000_000:
            return {'ZEBRA': 4000, 'TRANSITION': 2500, 'DANGER': 1500}[mode], 9
        elif b >= 1_800_000:
            return {'ZEBRA': 3000, 'TRANSITION': 2000, 'DANGER': 1200}[mode], 9
        elif b >= 1_000_000:
            return {'ZEBRA': 2000, 'TRANSITION': 1500, 'DANGER': 1000}[mode], 9
        else:
            return {'ZEBRA': 1000, 'TRANSITION': 1000, 'DANGER': 1000}[mode], 10
    elif profile == 'SHIELD_CONSERVATIVE':
        if b >= 3_000_000:
            return {'ZEBRA': 2000, 'TRANSITION': 1200, 'DANGER': 1000}[mode], 10
        elif b >= 1_800_000:
            return {'ZEBRA': 1500, 'TRANSITION': 1000, 'DANGER': 1000}[mode], 10
        else:
            return {'ZEBRA': 1000, 'TRANSITION': 1000, 'DANGER': 1000}[mode], 10
    else: # APEX_IDEAL
        if b >= 3_000_000:
            return {'ZEBRA': 3000, 'TRANSITION': 1800, 'DANGER': 1000}[mode], 10
        elif b >= 1_800_000:
            return {'ZEBRA': 2000, 'TRANSITION': 1500, 'DANGER': 1000}[mode], 10
        elif b >= 1_000_000:
            return {'ZEBRA': 1500, 'TRANSITION': 1200, 'DANGER': 1000}[mode], 10
        else:
            return {'ZEBRA': 1000, 'TRANSITION': 1000, 'DANGER': 1000}[mode], 10

def calculate_bet_v12_4(step, cdt, mode, profile, bankroll, prev_bet=None):
    base_b0, target_steps = get_calibrated_base_bet(profile, mode, bankroll)
    terminal_cap = min(1_000_000, math.floor(bankroll / 1.90))
    terminal_cap = max(1000, terminal_cap)
    
    if step <= 1 or cdt <= 0:
        return max(1000, min(base_b0, bankroll))
        
    remaining = max(1, target_steps - step + 1)
    
    # Terminal step reached
    if remaining == 1:
        return max(1000, min(terminal_cap, bankroll))
        
    prev_b = prev_bet if (prev_bet is not None and prev_bet > 0) else base_b0
    ratio = terminal_cap / max(1, prev_b)
    dynamic_x = max(2.025, min(2.40, math.pow(ratio, 1.0 / remaining)))
    geom_bet = round(prev_b * dynamic_x)
    
    # Strict debt coverage under 2% tax
    min_tbb = math.ceil((cdt + base_b0) / 0.98)
    bet = max(min_tbb, geom_bet)
    
    # 980k Horizon Guard on penultimate step (remaining == 2)
    if remaining == 2 and terminal_cap >= 900_000:
        max_safe = max(min_tbb, 975_000 - cdt)
        bet = min(bet, max_safe)
        
    final_bet = max(1000, min(bet, 1_000_000, bankroll))
    return int(round(final_bet))

# Load all 15 sessions
session_paths = glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json')
session_paths.append(r'd:\Downloads\matreshka_quantum_v11_2026-11-08.json')
session_paths.append(r'd:\Downloads\matreshka_session_2026-11-08.json')
session_paths.append(r'd:\Downloads\matreshka_session_2026-11-08 (1).json')

sessions_data = []
for p in session_paths:
    if not os.path.exists(p): continue
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    outcomes = []
    for l in d.get('logs', []):
        res = l.get('input_result') or l.get('actual_outcome')
        if res: outcomes.append(res)
    if outcomes:
        sessions_data.append({'name': os.path.basename(p), 'outcomes': outcomes})

def run_suite(profile, init_b=3_806_838):
    total_net = 0
    won = 0
    max_dd = 0
    limit_hits = 0
    max_step = 0
    
    for sess in sessions_data:
        pred = MPDPredictor()
        bank = init_b
        cdt = 0
        step = 1
        peak = bank
        sess_max_dd = 0
        prev_b = 0
        
        for outcome in sess['outcomes']:
            rec = pred.get_recommendation()
            
            # Mode detection
            non_zero = [x for x in pred.history if x != 'ZERO']
            cur_streak = 0
            if non_zero:
                lc = non_zero[-1]
                for x in reversed(non_zero):
                    if x == lc: cur_streak += 1
                    else: break
            recent_nz = non_zero[-6:]
            alt_cnt = sum(1 for i in range(1, len(recent_nz)) if recent_nz[i] != recent_nz[i-1]) if len(recent_nz) > 1 else 0
            fast_alt = alt_cnt / max(1, len(recent_nz) - 1)
            slow_nz = non_zero[-15:]
            slow_alt_cnt = sum(1 for i in range(1, len(slow_nz)) if slow_nz[i] != slow_nz[i-1]) if len(slow_nz) > 1 else 0
            slow_alt = slow_alt_cnt / max(1, len(slow_nz) - 1)
            streak3_cnt = 0
            if slow_nz:
                sl_c = 1
                sl_col = slow_nz[0]
                for s_i in range(1, len(slow_nz)):
                    if slow_nz[s_i] == sl_col: sl_c += 1
                    else:
                        if sl_c >= 3: streak3_cnt += 1
                        sl_c = 1
                        sl_col = slow_nz[s_i]
                if sl_c >= 3: streak3_cnt += 1
            z10 = pred.history[-10:].count('ZERO')
            
            score = 0
            if cur_streak >= 7: score -= 8
            elif cur_streak == 6: score -= 6
            elif cur_streak == 5: score -= 4
            elif cur_streak == 4: score -= 1
            elif cur_streak <= 2: score += 2
            if fast_alt >= 0.80: score += 3
            elif fast_alt >= 0.60: score += 1
            elif fast_alt < 0.30: score -= 2
            if slow_alt >= 0.70: score += 1
            elif slow_alt < 0.40: score -= 1
            if streak3_cnt >= 3: score -= 2
            elif streak3_cnt == 2: score -= 1
            elif streak3_cnt == 0: score += 1
            if z10 >= 3: score -= 3
            elif z10 == 2: score -= 1
            
            if score >= 2: mode = 'ZEBRA'
            elif score <= -2: mode = 'DANGER'
            else: mode = 'TRANSITION'
            
            bet = calculate_bet_v12_4(step, cdt, mode, profile, bank, prev_b if step > 1 else None)
            
            if bet >= 1_000_000:
                limit_hits += 1
                bet = 1_000_000
                
            max_step = max(max_step, step)
            
            is_win = (outcome == rec and outcome != 'ZERO')
            if is_win:
                win_profit = int(round(bet * 0.98))
                bank += win_profit
                cdt = 0
                step = 1
                prev_b = 0
            else:
                bank -= bet
                cdt += bet
                step += 1
                prev_b = bet
                
            pred.add_result(outcome)
            if bank > peak: peak = bank
            dd = peak - bank
            if dd > sess_max_dd: sess_max_dd = dd
            
            if bank < 1000:
                break
                
        net_sess = bank - init_b
        total_net += net_sess
        if net_sess > 0: won += 1
        if sess_max_dd > max_dd: max_dd = sess_max_dd
        print(f"  {sess['name'][:32]:<32} | Spins: {len(sess['outcomes']):3d} | Net: {net_sess:+10,d} RUB | MaxDD: {sess_max_dd:8,d} RUB")
        
    print(f"\n[{profile}] TOTAL NET PROFIT: {total_net:+12,d} RUB | WON: {won}/{len(sessions_data)} ({won/len(sessions_data)*100:.1f}%) | MaxDD: {max_dd:9,d} RUB | Limit Hits: {limit_hits} | MaxStep: {max_step}")

print("="*85)
print("TESTING SUITE: APEX_IDEAL")
print("="*85)
run_suite('APEX_IDEAL')
print("="*85)
print("TESTING SUITE: TURBO_HARVEST")
print("="*85)
run_suite('TURBO_HARVEST')
print("="*85)
print("TESTING SUITE: SHIELD_CONSERVATIVE")
print("="*85)
run_suite('SHIELD_CONSERVATIVE')
