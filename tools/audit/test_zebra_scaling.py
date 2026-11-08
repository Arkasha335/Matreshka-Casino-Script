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

def run_test_zebra(zb0, tb0, db0, n_steps=10):
    total_net = 0
    won = 0
    max_dd = 0
    limit_hits = 0
    initial_b = 3_806_838
    
    for sess in sessions_data:
        pred = MPDPredictor()
        bank = initial_b
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
            
            if mode == 'ZEBRA':
                base_b0 = zb0
            elif mode == 'TRANSITION':
                base_b0 = tb0
            else:
                base_b0 = db0
                
            terminal_cap = min(1_000_000, math.floor(bank / 1.90))
            terminal_cap = max(1000, terminal_cap)
            
            if step <= 1 or cdt <= 0:
                bet = base_b0
            else:
                remaining = max(1, n_steps - step + 1)
                if remaining == 1:
                    bet = min(terminal_cap, bank)
                else:
                    prev_bet = prev_b if prev_b > 0 else base_b0
                    ratio = terminal_cap / max(1, prev_bet)
                    dynamic_x = max(2.025, min(2.40, math.pow(ratio, 1.0 / remaining)))
                    geom_bet = round(prev_bet * dynamic_x)
                    min_tbb = math.ceil((cdt + base_b0) / 0.98)
                    bet = max(min_tbb, geom_bet)
                    # 980k guard
                    if remaining == 2 and terminal_cap >= 900_000:
                        max_safe = max(min_tbb, 970_000 - cdt)
                        bet = min(bet, max_safe)
                        
            final_bet = max(1000, min(bet, 1_000_000, bank))
            if final_bet >= 1_000_000:
                limit_hits += 1
                final_bet = 1_000_000
                
            is_win = (outcome == rec and outcome != 'ZERO')
            if is_win:
                win_profit = int(round(final_bet * 0.98))
                bank += win_profit
                cdt = 0
                step = 1
                prev_b = 0
            else:
                bank -= final_bet
                cdt += final_bet
                step += 1
                prev_b = final_bet
                
            pred.add_result(outcome)
            if bank > peak: peak = bank
            dd = peak - bank
            if dd > sess_max_dd: sess_max_dd = dd
            
            if bank < 1000:
                break
                
        net_sess = bank - initial_b
        total_net += net_sess
        if net_sess > 0: won += 1
        if sess_max_dd > max_dd: max_dd = sess_max_dd
        
    print(f"Z:{zb0:4d} T:{tb0:4d} D:{db0:4d} | Net: {total_net:+11,d} RUB | Won: {won}/{len(sessions_data)} ({won/len(sessions_data)*100:.0f}%) | MaxDD: {max_dd:8,d} RUB | Limit Hits: {limit_hits}")

print(f"{'Configuration':<22} | {'Net Profit':<15} | {'Win Rate':<14} | {'Max Drawdown':<12} | {'Limit Hits'}")
print("="*80)
run_test_zebra(2000, 1000, 1000)
run_test_zebra(2500, 1500, 1000)
run_test_zebra(3000, 1500, 1000)
run_test_zebra(3500, 2000, 1000)
run_test_zebra(4000, 2000, 1000)
run_test_zebra(4000, 2500, 1000)
run_test_zebra(5000, 2500, 1000)
