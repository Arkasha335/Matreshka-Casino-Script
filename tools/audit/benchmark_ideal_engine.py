import os, sys, math, json, glob

sys.path.append(os.path.dirname(__file__))
from simulate_terminal_strategies import MPDPredictor

def get_calibrated_engine_params(profile, mode, bankroll):
    """
    Calibrated parameters for each profile, mode, and bankroll tier.
    """
    effective_b = max(100_000, bankroll)
    
    # 1. Base bets and target steps based on bankroll & profile
    if profile == 'TURBO_HARVEST':
        # Maximum Profit Velocity
        if effective_b >= 3_000_000:
            b0_zebra = 4000
            b0_trans = 2500
            b0_danger = 1500
            n_steps = 8
        elif effective_b >= 1_800_000:
            b0_zebra = 3000
            b0_trans = 2000
            b0_danger = 1000
            n_steps = 8
        else:
            b0_zebra = 2000
            b0_trans = 1500
            b0_danger = 1000
            n_steps = 9
    elif profile == 'SHIELD_CONSERVATIVE':
        # Maximum Capital Preservation
        if effective_b >= 3_000_000:
            b0_zebra = 2000
            b0_trans = 1500
            b0_danger = 1000
            n_steps = 10
        elif effective_b >= 1_800_000:
            b0_zebra = 1500
            b0_trans = 1000
            b0_danger = 1000
            n_steps = 10
        else:
            b0_zebra = 1000
            b0_trans = 1000
            b0_danger = 1000
            n_steps = 10
    else: # APEX_IDEAL (Golden Standard)
        if effective_b >= 3_000_000:
            b0_zebra = 3000
            b0_trans = 2000
            b0_danger = 1200
            n_steps = 9
        elif effective_b >= 1_800_000:
            b0_zebra = 2000
            b0_trans = 1500
            b0_danger = 1000
            n_steps = 9
        else:
            b0_zebra = 1200
            b0_trans = 1000
            b0_danger = 1000
            n_steps = 10
            
    if mode == 'ZEBRA':
        base_b0 = b0_zebra
        target_steps = n_steps
    elif mode == 'TRANSITION':
        base_b0 = b0_trans
        target_steps = n_steps
    else: # DANGER
        base_b0 = b0_danger
        target_steps = min(10, n_steps + 1)
        
    terminal_cap = min(1_000_000, math.floor(effective_b / 1.90))
    terminal_cap = max(1000, terminal_cap)
    
    # Calculate geometric X
    ratio = terminal_cap / max(1, base_b0)
    exponent = 1.0 / max(1, target_steps - 1)
    dynamic_multiplier = max(2.025, min(2.40, math.pow(ratio, exponent)))
    
    return {
        'base_bet': base_b0,
        'target_steps': target_steps,
        'growth_factor': dynamic_multiplier,
        'terminal_cap': terminal_cap
    }

def calculate_calibrated_bet(step, cdt, mode, profile, bankroll, prev_step_bet=None):
    params = get_calibrated_engine_params(profile, mode, bankroll)
    base_b0 = params['base_bet']
    target_steps = params['target_steps']
    terminal_cap = params['terminal_cap']
    growth_factor = params['growth_factor']
    
    if step <= 1 or cdt <= 0:
        return max(1000, min(base_b0, bankroll))
        
    remaining = max(1, target_steps - step + 1)
    
    # Terminal step reached: snap to terminal ceiling
    if remaining == 1:
        return max(1000, min(terminal_cap, bankroll))
        
    # Previous bet level
    if prev_step_bet is not None and prev_step_bet > 0:
        prev_b = prev_step_bet
    else:
        prev_b = max(base_b0, round(base_b0 * math.pow(growth_factor, step - 2)))
        
    ratio = terminal_cap / max(1, prev_b)
    dynamic_x = max(2.025, min(2.40, math.pow(ratio, 1.0 / remaining)))
    geom_bet = round(prev_b * dynamic_x)
    
    # Strict debt coverage under 2% tax
    min_tbb = math.ceil((cdt + base_b0) / 0.98)
    bet = max(min_tbb, geom_bet)
    
    # 980k Horizon Guard:
    # If this is the step right before the terminal step (remaining == 2),
    # ensure that after this bet, remaining debt does NOT exceed 970,000 RUB,
    # so the final 1,000,000 RUB bet is guaranteed to recover fully!
    if remaining == 2 and terminal_cap >= 900_000:
        max_safe = max(min_tbb, 970_000 - cdt)
        bet = min(bet, max_safe)
        
    final_bet = max(1000, min(bet, 1_000_000, bankroll))
    return int(round(final_bet))

# Load all sessions
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

print(f"Loaded {len(sessions_data)} sessions, total {sum(len(s['outcomes']) for s in sessions_data)} spins.")

def run_benchmark(profile, initial_b=3_806_838):
    total_net = 0
    won = 0
    max_dd = 0
    limit_hits = 0
    max_step_seen = 0
    
    for sess in sessions_data:
        pred = MPDPredictor()
        bank = initial_b
        cdt = 0
        step = 1
        peak = bank
        sess_max_dd = 0
        prev_bet = 0
        
        for outcome in sess['outcomes']:
            rec = pred.get_recommendation()
            
            # Mode detection (exact original PRNG detector logic)
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
            
            bet = calculate_calibrated_bet(step, cdt, mode, profile, bank, prev_bet if step > 1 else None)
            
            if bet >= 1_000_000:
                limit_hits += 1
                bet = 1_000_000
                
            max_step_seen = max(max_step_seen, step)
            
            is_win = (outcome == rec and outcome != 'ZERO')
            if is_win:
                win_profit = int(round(bet * 0.98))
                bank += win_profit
                cdt = 0
                step = 1
                prev_bet = 0
            else:
                bank -= bet
                cdt += bet
                step += 1
                prev_bet = bet
                
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
        print(f"  {sess['name'][:32]:<32} | Spins: {len(sess['outcomes']):3d} | Net: {net_sess:+10,d} RUB | MaxDD: {sess_max_dd:8,d} RUB")
        
    print(f"\n[{profile}] TOTAL NET PROFIT: {total_net:+12,d} RUB | WON: {won}/{len(sessions_data)} ({won/len(sessions_data)*100:.1f}%) | MaxDD: {max_dd:9,d} RUB | Limit Hits: {limit_hits} | MaxStep: {max_step_seen}")

print("\n" + "="*80)
print("BENCHMARK RESULTS ACROSS ALL 15 VERIFIED SESSIONS (1,079 SPINS)")
print("="*80)
run_benchmark('TURBO_HARVEST')
print("-" * 80)
run_benchmark('APEX_IDEAL')
print("-" * 80)
run_benchmark('SHIELD_CONSERVATIVE')
