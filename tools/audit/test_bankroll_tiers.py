import os, sys, math, json
sys.path.append(os.path.dirname(__file__))
from simulate_terminal_strategies import MPDPredictor, sessions

def run_bankroll_scaled_benchmark():
    print("=" * 100)
    print("BANKROLL SCALED PARAMETERS BENCHMARK (14 SESSIONS, 1046 SPINS)")
    print("=" * 100)
    
    # Testing different scaling formulas:
    # W >= 3M: high tier
    # W 2M-3M: mid tier
    # W < 2M: safe tier
    
    tier_configs = [
        # (name, zebra_b0_hi, zebra_b0_mid, zebra_b0_lo, zebra_n, trans_b0, trans_n, danger_b0, danger_n)
        ("Apex Balanced 10-10-11", 1800, 1500, 1000, 10, 1000, 10, 1000, 11),
        ("Apex High-Velocity 9-10-11", 1800, 1500, 1000, 9, 1000, 10, 1000, 11),
        ("Apex Max-Profit 9-10-11 (2k)", 2000, 1500, 1000, 9, 1000, 10, 1000, 11),
        ("Apex Ultra 10-10-11 (2k)", 2000, 1500, 1000, 10, 1000, 10, 1000, 11),
        ("Apex Shield 10-11-11", 1500, 1200, 1000, 10, 1000, 11, 1000, 11),
        ("Apex Conservative 10-10-10", 1200, 1000, 1000, 10, 1000, 10, 1000, 10),
    ]
    
    for name, z_hi, z_mid, z_lo, z_n, t_b0, t_n, d_b0, d_n in tier_configs:
        total_net = 0
        won = 0
        max_dd = 0
        max_step = 0
        limit_hits = 0
        initial_bankroll = 3_806_838
        
        for sess in sessions:
            pred = MPDPredictor()
            bank = initial_bankroll
            cdt = 0
            step = 1
            peak = bank
            sess_max_dd = 0
            
            for outcome in sess['outcomes']:
                rec = pred.get_recommendation()
                
                # Mode detection (same exact logic as prng-detector)
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
                
                # Dynamic B0 based on bankroll tier:
                if mode == 'ZEBRA':
                    if bank >= 3_000_000: cur_b0 = z_hi
                    elif bank >= 2_000_000: cur_b0 = z_mid
                    else: cur_b0 = z_lo
                    target_steps = z_n
                elif mode == 'TRANSITION':
                    cur_b0 = t_b0
                    target_steps = t_n
                else:
                    cur_b0 = d_b0
                    target_steps = d_n
                    
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
                    
                max_step = max(max_step, step)
                
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
                
            net_sess = bank - initial_bankroll
            total_net += net_sess
            if net_sess > 0: won += 1
            if sess_max_dd > max_dd: max_dd = sess_max_dd
            
        print(f"{name:<28} | Net: {total_net:+11d} RUB | Won: {won}/{len(sessions)} ({won/len(sessions)*100:.0f}%) | MaxDD: {max_dd:7d} RUB | Limit Hits: {limit_hits} | MaxStep: {max_step}")

run_bankroll_scaled_benchmark()
