import os, sys, math, json
sys.path.append(os.path.dirname(__file__))
from simulate_terminal_strategies import MPDPredictor, sessions

def test_zebra_n9_range():
    print("=" * 90)
    print("TESTING ZEBRA N=9 WITH DIFFERENT BANKROLLS")
    print("=" * 90)
    
    bankrolls = [1_500_000, 2_000_000, 2_500_000, 3_000_000, 3_806_838, 5_000_000]
    
    for init_b in bankrolls:
        total_net = 0
        won = 0
        max_dd = 0
        limit_hits = 0
        
        for sess in sessions:
            pred = MPDPredictor()
            bank = init_b
            cdt = 0
            step = 1
            peak = bank
            sess_max_dd = 0
            
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
                
                # Calibrated Bankroll tiers
                if mode == 'ZEBRA':
                    if bank >= 3_000_000:
                        cur_b0 = 2000
                        target_steps = 9  # High profit velocity in calm zebra
                    elif bank >= 2_000_000:
                        cur_b0 = 1500
                        target_steps = 10
                    else:
                        cur_b0 = 1000
                        target_steps = 10
                elif mode == 'TRANSITION':
                    cur_b0 = 1000
                    target_steps = 10  # 10 steps cushion for streaks 3-4
                else: # DANGER
                    cur_b0 = 1000
                    target_steps = 11  # 11 steps shield for anomalies
                    
                terminal_cap = min(1_000_000, math.floor(bank / 1.90))
                terminal_cap = max(1000, terminal_cap)
                
                if step == 1 or cdt <= 0:
                    current_bet = max(1000, cur_b0)
                else:
                    m = max(1, target_steps - step + 1)
                    if m == 1:
                        current_bet = min(terminal_cap, bank)
                    else:
                        prev_bet = current_bet
                        ratio = terminal_cap / max(1, prev_bet)
                        if ratio > 1:
                            x = ratio ** (1.0 / m)
                            current_bet = round(prev_bet * x)
                        min_tbb = math.ceil((cdt + cur_b0) / 0.98)
                        current_bet = max(min_tbb, current_bet)
                        current_bet = max(1000, min(1_000_000, current_bet, bank))
                        
                if current_bet >= 1_000_000:
                    limit_hits += 1
                    current_bet = 1_000_000
                    
                is_win = (outcome == rec and outcome != 'ZERO')
                if is_win:
                    win_profit = int(round(current_bet * 0.98))
                    bank += win_profit
                    cdt = 0
                    step = 1
                else:
                    bank -= current_bet
                    cdt += current_bet
                    step += 1
                    
                pred.add_result(outcome)
                if bank > peak: peak = bank
                dd = peak - bank
                if dd > sess_max_dd: sess_max_dd = dd
                
            net_sess = bank - init_b
            total_net += net_sess
            if net_sess > 0: won += 1
            if sess_max_dd > max_dd: max_dd = sess_max_dd
            
        print(f"Bankroll: {init_b:10,d} RUB | Net: {total_net:+11,d} RUB | Won: {won:2d}/{len(sessions)} ({won/len(sessions)*100:5.1f}%) | MaxDD: {max_dd:9,d} RUB | Hits: {limit_hits}")

test_zebra_n9_range()
