import glob
import json
import math
import os
import sys

sys.path.append(os.path.dirname(__file__))
from simulate_terminal_strategies import MPDPredictor, sessions

print(f"Total verified sessions: {len(sessions)}, total spins: {sum(len(s['outcomes']) for s in sessions)}")

def simulate_strategy(b0_zebra, n_zebra, b0_trans, n_trans, b0_danger, n_danger, initial_bankroll=3_806_838):
    """
    Simulates the exact engine behavior on all sessions:
    - Reading logic: MPDPredictor (unmodified!)
    - Mode detection: detectMode / score from prng-detector
    - Mode-specific (B0, N) parameters
    - Strict 50-slot, 2% tax, integer rounding, min 1000, max 1,000,000
    """
    total_net = 0
    sessions_won = 0
    max_step_overall = 0
    limit_hits = 0
    max_drawdown = 0

    for sess in sessions:
        pred = MPDPredictor()
        bank = initial_bankroll
        cdt = 0
        step = 1
        peak = bank
        sess_max_dd = 0
        
        for outcome in sess['outcomes']:
            # Exact recommendation from MPDPredictor
            rec = pred.get_recommendation()
            
            # Mode detection from non-zero history
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
            
            if score >= 2:
                mode = 'ZEBRA'
            elif score <= -2:
                mode = 'DANGER'
            else:
                mode = 'TRANSITION'
                
            # Mode parameters
            if mode == 'ZEBRA':
                mode_b0, target_steps = b0_zebra, n_zebra
            elif mode == 'TRANSITION':
                mode_b0, target_steps = b0_trans, n_trans
            else:
                mode_b0, target_steps = b0_danger, n_danger
                
            # Bankroll scaling
            terminal_cap = min(1_000_000, math.floor(bank / 1.90))
            terminal_cap = max(1000, terminal_cap)
            
            if step == 1 or cdt <= 0:
                current_bet = max(1000, mode_b0)
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
                    min_tbb = math.ceil((cdt + mode_b0) / 0.98)
                    current_bet = max(min_tbb, current_bet)
                    current_bet = max(1000, min(1_000_000, current_bet, bank))
                    
            if current_bet >= 1_000_000:
                limit_hits += 1
                current_bet = 1_000_000
                
            max_step_overall = max(max_step_overall, step)
            
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
            
            if bank < 1000:
                break
                
        net_sess = bank - initial_bankroll
        total_net += net_sess
        if net_sess > 0: sessions_won += 1
        if sess_max_dd > max_drawdown: max_drawdown = sess_max_dd
        
    return {
        'net': total_net,
        'won': sessions_won,
        'total_sess': len(sessions),
        'max_step': max_step_overall,
        'limit_hits': limit_hits,
        'max_dd': max_drawdown
    }

# Grid Search over calibrations
print("\n" + "="*95)
print(f"{'ZEBRA (B0, N)':<18} | {'TRANS (B0, N)':<18} | {'DANGER (B0, N)':<18} | {'NET PROFIT':<14} | {'WON':<8} | {'MaxDD':<10} | {'Hits'}")
print("="*95)

candidates = [
    # Baseline
    ((1000, 10), (1000, 10), (1000, 10)),
    ((1200, 10), (1000, 10), (1000, 10)),
    ((1500, 10), (1000, 10), (1000, 10)),
    ((1600, 10), (1000, 10), (1000, 10)),
    ((1800, 10), (1000, 10), (1000, 10)),
    ((2000, 10), (1000, 10), (1000, 10)),
    # Varying Transition
    ((1200, 10), (1000, 11), (1000, 10)),
    ((1500, 10), (1000, 11), (1000, 10)),
    ((1800, 10), (1000, 11), (1000, 10)),
    ((2000, 10), (1000, 11), (1000, 10)),
    # Varying Danger
    ((1200, 10), (1000, 10), (1000, 11)),
    ((1500, 10), (1000, 10), (1000, 11)),
    ((1800, 10), (1000, 10), (1000, 11)),
    ((2000, 10), (1000, 10), (1000, 11)),
    # High Zebra Velocity (9 steps Zebra vs 10 steps defense)
    ((1500, 9), (1000, 10), (1000, 11)),
    ((1800, 9), (1000, 10), (1000, 11)),
    ((2000, 9), (1000, 10), (1000, 11)),
]

for (zb0, zn), (tb0, tn), (db0, dn) in candidates:
    res = simulate_strategy(zb0, zn, tb0, tn, db0, dn)
    z_str = f"B0={zb0}, N={zn}"
    t_str = f"B0={tb0}, N={tn}"
    d_str = f"B0={db0}, N={dn}"
    print(f"{z_str:<18} | {t_str:<18} | {d_str:<18} | {res['net']:+12d} RUB | {res['won']}/{res['total_sess']} ({res['won']/res['total_sess']*100:.0f}%) | {res['max_dd']:8d} RUB | {res['limit_hits']}")
