import os, sys, math, json, glob
sys.path.append(os.path.dirname(__file__))
from simulate_terminal_strategies import MPDPredictor

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

def run_simulation(config_name, get_params_fn):
    total_net = 0
    won = 0
    max_dd = 0
    limit_hits = 0
    max_step = 0
    sess_results = []
    
    for sess in sessions_data:
        pred = MPDPredictor()
        bank = 3_806_838
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
            
            base_b0, target_steps = get_params_fn(mode, bank)
            terminal_cap = min(1_000_000, math.floor(bank / 1.90))
            terminal_cap = max(1000, terminal_cap)
            
            if step <= 1 or cdt <= 0:
                bet = max(1000, min(base_b0, bank))
            else:
                remaining = max(1, target_steps - step + 1)
                if remaining == 1:
                    bet = max(1000, min(terminal_cap, bank))
                else:
                    prev_b_val = prev_b if (prev_b > 0) else base_b0
                    ratio = terminal_cap / max(1, prev_b_val)
                    dynamic_x = max(2.025, min(2.40, math.pow(ratio, 1.0 / remaining)))
                    geom_bet = round(prev_b_val * dynamic_x)
                    min_tbb = math.ceil((cdt + base_b0) / 0.98)
                    bet = max(min_tbb, geom_bet)
                    
                    # 980k Horizon Guard on penultimate step: ensure remaining debt allows 1M terminal win
                    if remaining == 2 and terminal_cap >= 900_000:
                        safe_debt_limit = 975_000 - cdt
                        if safe_debt_limit > min_tbb:
                            bet = min(bet, safe_debt_limit)
                            
                bet = max(1000, min(bet, 1_000_000, bank))
            
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
                
        net_sess = bank - 3_806_838
        total_net += net_sess
        if net_sess > 0: won += 1
        if sess_max_dd > max_dd: max_dd = sess_max_dd
        sess_results.append((sess['name'], len(sess['outcomes']), net_sess, sess_max_dd))
        
    print(f"[{config_name}]")
    print(f"  Total Net Profit: {total_net:+12,d} RUB | Win Rate: {won}/{len(sessions_data)} ({won/len(sessions_data)*100:.1f}%)")
    print(f"  Max Drawdown:     {max_dd:12,d} RUB | Limit Hits: {limit_hits} | Max Step: {max_step}")
    latest_net = sess_results[-1][2]
    print(f"  Latest Session (1) Net: {latest_net:+8,d} RUB (Spins: {sess_results[-1][1]})")
    return total_net, won, max_dd

print("=================================================================")
# Config 1: ZEBRA=3000 (N=10), TRANSITION=1500 (N=10), DANGER=1000 (N=10)
def cfg1(mode, b):
    if b >= 3_000_000:
        return {'ZEBRA': (3000, 10), 'TRANSITION': (1500, 10), 'DANGER': (1000, 10)}[mode]
    elif b >= 1_800_000:
        return {'ZEBRA': (2000, 10), 'TRANSITION': (1200, 10), 'DANGER': (1000, 10)}[mode]
    else:
        return {'ZEBRA': (1000, 10), 'TRANSITION': (1000, 10), 'DANGER': (1000, 10)}[mode]

run_simulation("CFG 1: Z=3000 (N10), T=1500 (N10), D=1000 (N10)", cfg1)

print("-----------------------------------------------------------------")
# Config 2: ZEBRA=3000 (N=9), TRANSITION=1500 (N=10), DANGER=1000 (N=10)
def cfg2(mode, b):
    if b >= 3_000_000:
        return {'ZEBRA': (3000, 9), 'TRANSITION': (1500, 10), 'DANGER': (1000, 10)}[mode]
    elif b >= 1_800_000:
        return {'ZEBRA': (2000, 9), 'TRANSITION': (1200, 10), 'DANGER': (1000, 10)}[mode]
    else:
        return {'ZEBRA': (1000, 10), 'TRANSITION': (1000, 10), 'DANGER': (1000, 10)}[mode]

run_simulation("CFG 2: Z=3000 (N9), T=1500 (N10), D=1000 (N10)", cfg2)

print("-----------------------------------------------------------------")
# Config 3: ZEBRA=3500 (N=9), TRANSITION=1800 (N=10), DANGER=1000 (N=10)
def cfg3(mode, b):
    if b >= 3_000_000:
        return {'ZEBRA': (3500, 9), 'TRANSITION': (1800, 10), 'DANGER': (1000, 10)}[mode]
    elif b >= 1_800_000:
        return {'ZEBRA': (2500, 9), 'TRANSITION': (1500, 10), 'DANGER': (1000, 10)}[mode]
    else:
        return {'ZEBRA': (1000, 10), 'TRANSITION': (1000, 10), 'DANGER': (1000, 10)}[mode]

run_simulation("CFG 3: Z=3500 (N9), T=1800 (N10), D=1000 (N10)", cfg3)

print("-----------------------------------------------------------------")
# Config 4: ZEBRA=2500 (N=10), TRANSITION=1500 (N=10), DANGER=1000 (N=10)
def cfg4(mode, b):
    if b >= 3_000_000:
        return {'ZEBRA': (2500, 10), 'TRANSITION': (1500, 10), 'DANGER': (1000, 10)}[mode]
    elif b >= 1_800_000:
        return {'ZEBRA': (2000, 10), 'TRANSITION': (1200, 10), 'DANGER': (1000, 10)}[mode]
    else:
        return {'ZEBRA': (1000, 10), 'TRANSITION': (1000, 10), 'DANGER': (1000, 10)}[mode]

run_simulation("CFG 4: Z=2500 (N10), T=1500 (N10), D=1000 (N10)", cfg4)
