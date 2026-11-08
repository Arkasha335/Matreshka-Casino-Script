import os, sys, math, json

sys.path.append(os.path.dirname(__file__))
from simulate_terminal_strategies import MPDPredictor, sessions

print(f"Total sessions in benchmark: {len(sessions)}")

# Let's inspect the math of the Flexible Multiplier Ladder
def calculate_step_bet(step, cdt, mode, profile, bankroll):
    """
    Computes the optimal bet for current step, current CDT, active mode, and bankroll.
    Rules:
    - Min bet: 1,000 RUB
    - Max bet: 1,000,000 RUB
    - Terminal step lands on min(1,000,000, floor(bankroll / 1.90))
    - Cumulative debt before terminal step never exceeds 980,000 RUB
    """
    MIN_BET = 1000
    MAX_BET = 1000000
    
    # 1. Bankroll-scaled base bets per profile & mode:
    # High Bankroll (>= 3.0M):
    if bankroll >= 3_000_000:
        if profile == 'TURBO_HARVEST':
            b0_zebra = 4000
            b0_trans = 2500
            b0_danger = 1500
            n_target = 8  # 8 steps to 1M
        elif profile == 'APEX_IDEAL':
            b0_zebra = 3000
            b0_trans = 2000
            b0_danger = 1200
            n_target = 9  # 9 steps to 1M
        else: # SHIELD_CONSERVATIVE
            b0_zebra = 2000
            b0_trans = 1500
            b0_danger = 1000
            n_target = 10 # 10 steps to 1M
    elif bankroll >= 1_800_000:
        if profile == 'TURBO_HARVEST':
            b0_zebra = 2500
            b0_trans = 1800
            b0_danger = 1000
            n_target = 8
        elif profile == 'APEX_IDEAL':
            b0_zebra = 2000
            b0_trans = 1500
            b0_danger = 1000
            n_target = 9
        else:
            b0_zebra = 1500
            b0_trans = 1000
            b0_danger = 1000
            n_target = 10
    else: # Bankroll < 1.8M
        b0_zebra = 1500 if bankroll >= 1_000_000 else 1000
        b0_trans = 1000
        b0_danger = 1000
        n_target = 10 if bankroll >= 1_000_000 else 11

    # Active mode parameters
    if mode == 'ZEBRA':
        base_b0 = b0_zebra
        # In zebra, target steps
        target_steps = n_target
    elif mode == 'TRANSITION':
        base_b0 = b0_trans
        # Transition gives +1 cushion step if needed
        target_steps = n_target
    else: # DANGER
        base_b0 = b0_danger
        # Danger grants +1 extra step of safety cushion
        target_steps = n_target + 1

    terminal_cap = min(MAX_BET, math.floor(bankroll / 1.90))
    terminal_cap = max(MIN_BET, terminal_cap)

    if step <= 1 or cdt <= 0:
        return max(MIN_BET, min(base_b0, bankroll))

    # Remaining steps in progression
    remaining = max(1, target_steps - step + 1)
    
    # If this is the terminal step:
    if remaining == 1:
        # Snap directly to terminal cap
        return max(MIN_BET, min(terminal_cap, bankroll))
        
    # If remaining == 2 (the step right before terminal):
    # CRITICAL CHECK: Total debt after this step must NOT exceed 980,000 RUB!
    # Because terminal step is at most 1,000,000 RUB, which yields 980,000 net win.
    # Therefore: cdt + bet_next_to_last <= 980,000 - min_profit
    # So bet_next_to_last <= min(geometric_bet, 980,000 - cdt - base_b0)
    
    # Calculate geometric multiplier to span from current debt level to terminal_cap
    # We want bet to smoothly ramp up
    # If we have 'remaining' steps:
    # bet * X^(remaining - 1) = terminal_cap
    # Also, we must cover CDT: min_tbb = ceil((cdt + base_b0) / 0.98)
    min_tbb = math.ceil((cdt + base_b0) / 0.98)
    
    # Geometric target
    # Ratio to terminal cap:
    ratio = terminal_cap / max(1, min_tbb)
    if ratio > 1.0 and remaining > 1:
        x_exp = 1.0 / remaining
        geom_x = math.pow(ratio, x_exp)
        geom_bet = round(min_tbb * geom_x)
    else:
        geom_bet = min_tbb
        
    candidate_bet = max(min_tbb, geom_bet)
    
    # Safety constraint: if remaining == 2, do NOT exceed headroom for final step!
    if remaining == 2:
        max_safe_for_penultimate = max(min_tbb, 970_000 - cdt)
        candidate_bet = min(candidate_bet, max_safe_for_penultimate)
        
    final_bet = max(MIN_BET, min(candidate_bet, MAX_BET, bankroll))
    return int(round(final_bet))

print("Simulation function defined successfully.")

def run_benchmark_on_sessions(profile_name, initial_b=3_806_838):
    total_net = 0
    won = 0
    max_dd = 0
    limit_hits = 0
    max_step_overall = 0
    
    # Include all 14 archive sessions + the new session
    all_session_paths = glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json')
    all_session_paths.append(r'd:\Downloads\matreshka_quantum_v11_2026-11-08.json')
    all_session_paths.append(r'd:\Downloads\matreshka_session_2026-11-08.json')
    all_session_paths.append(r'd:\Downloads\matreshka_session_2026-11-08 (1).json')
    
    sess_list = []
    for fp in all_session_paths:
        if not os.path.exists(fp): continue
        with open(fp, 'r', encoding='utf-8') as f:
            d = json.load(f)
        outcomes = []
        for l in d.get('logs', []):
            res = l.get('input_result') or l.get('actual_outcome')
            if res: outcomes.append(res)
        if outcomes:
            sess_list.append({'name': os.path.basename(fp), 'outcomes': outcomes})
            
    print(f"\n--- BENCHMARK: Profile {profile_name} (Total Sessions: {len(sess_list)}) ---")
    
    for sess in sess_list:
        pred = MPDPredictor()
        bank = initial_b
        cdt = 0
        step = 1
        peak = bank
        sess_max_dd = 0
        sess_step_max = 0
        
        for outcome in sess['outcomes']:
            rec = pred.get_recommendation()
            
            # Mode detection (exact proven logic)
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
            
            bet = calculate_step_bet(step, cdt, mode, profile_name, bank)
            
            if bet >= 1_000_000:
                limit_hits += 1
                bet = 1_000_000
                
            sess_step_max = max(sess_step_max, step)
            max_step_overall = max(max_step_overall, step)
            
            is_win = (outcome == rec and outcome != 'ZERO')
            if is_win:
                win_profit = int(round(bet * 0.98))
                bank += win_profit
                cdt = 0
                step = 1
            else:
                bank -= bet
                cdt += bet
                step += 1
                
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
        print(f"  {sess['name'][:32]:<32} | Spins: {len(sess['outcomes']):3d} | Net: {net_sess:+10,d} RUB | MaxStep: {sess_step_max} | MaxDD: {sess_max_dd:8,d} RUB")
        
    print(f"TOTAL PROFIT: {total_net:+12,d} RUB | WON: {won}/{len(sess_list)} ({won/len(sess_list)*100:.1f}%) | MaxDD: {max_dd:9,d} RUB | Limit Hits: {limit_hits}")

import glob
run_benchmark_on_sessions('TURBO_HARVEST')
run_benchmark_on_sessions('APEX_IDEAL')
run_benchmark_on_sessions('SHIELD_CONSERVATIVE')
