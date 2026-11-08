import json
import glob
import os
import math
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

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

# v10.4 pattern predictor
def get_recommendation_v10(history):
    if len(history) == 0:
        return 'RED', 50, 'АНАЛИЗ'
    non_zero = [h for h in history if h['outcome'] != 'ZERO']
    if len(non_zero) >= 4:
        L1 = non_zero[-1]['outcome']
        L2 = non_zero[-2]['outcome']
        L3 = non_zero[-3]['outcome']
        L4 = non_zero[-4]['outcome']
        if L1 == L3 and L2 == L4 and L1 != L2:
            return ('BLACK' if L1 == 'RED' else 'RED'), 82, 'ЭХО-ПАТТЕРН'
        if L1 == L2 and L2 == L3 and L4 != L1:
            return ('BLACK' if L1 == 'RED' else 'RED'), 78, 'ВОЛНА (СЛОМ СЕРИИ)'
    if len(non_zero) < 2:
        return (non_zero[-1]['outcome'] if len(non_zero) > 0 else 'RED'), 50, 'АНАЛИЗ'
        
    L1 = non_zero[-1]['outcome']
    L2 = non_zero[-2]['outcome']
    
    # Simple apex streak
    active_streak = 0
    active_col = non_zero[-1]['outcome']
    for i in range(len(non_zero)-1, -1, -1):
        if non_zero[i]['outcome'] == active_col:
            active_streak += 1
        else:
            break
            
    # Max streak in window 20
    w20 = non_zero[-20:]
    max_s = 0
    c_s = 0
    c_c = None
    for h in w20:
        if h['outcome'] == c_c:
            c_s += 1
        else:
            c_c = h['outcome']
            c_s = 1
        if c_s > max_s:
            max_s = c_s
            
    if active_streak >= max_s and max_s > 0:
        return ('BLACK' if active_col == 'RED' else 'RED'), 90, 'ОТСКОК ОТ ПОТОЛКА'
    elif L1 == L2:
        return ('BLACK' if L1 == 'RED' else 'RED'), 50, 'НЕЙТРАЛЬНО'
    else:
        nz6 = non_zero[-6:]
        alt = sum(1 for i in range(1, len(nz6)) if nz6[i]['outcome'] != nz6[i-1]['outcome'])
        alt_rate = alt / max(1, len(nz6) - 1)
        rec = L1 if alt_rate < 0.80 else ('BLACK' if L1 == 'RED' else 'RED')
        return rec, 60, 'ЧЕРЕДОВАНИЕ'

def simulate_strategy(base_bet_formula, growth_factor, sniper_mult, max_table_limit=1000000):
    total_profit = 0
    total_limit_hits = 0
    session_drawdowns = []
    
    for sname, sdata in sessions.items():
        initial_b = sdata["initial"]
        bal = float(initial_b)
        peak = bal
        max_dd = 0
        cdt = 0
        step = 1
        history = []
        limit_hits = 0
        
        base_b = base_bet_formula(initial_b)
        
        for out in sdata["outcomes"]:
            rec, conf, pat = get_recommendation_v10(history)
            
            if cdt <= 0:
                bet = round(base_b)
            else:
                tbb = round((cdt + base_b) / 0.98)
                geom = round(base_b * (growth_factor ** (step - 1)))
                if cdt > base_b * 2 and step >= 2 and sniper_mult > 1.0:
                    bet = max(round(tbb * sniper_mult), geom)
                else:
                    bet = max(tbb, geom)
                    
            if bet >= max_table_limit:
                bet = max_table_limit
                limit_hits += 1
                
            if bet > bal:
                bet = bal
                
            is_win = (out == rec and out != 'ZERO')
            if is_win:
                pnl = bet * 0.98
                bal += pnl
                cdt = max(0.0, cdt - pnl)
                if cdt < 10.0:
                    cdt = 0.0
                    step = 1
            else:
                pnl = -bet
                bal -= pnl
                cdt += bet
                step += 1
                
            if bal > peak:
                peak = bal
            dd = peak - bal
            if dd > max_dd:
                max_dd = dd
                
            history.append({'outcome': out, 'betAmount': bet, 'betColor': rec})
            if bal <= 0:
                break
                
        total_profit += (bal - initial_b)
        total_limit_hits += limit_hits
        session_drawdowns.append((max_dd / initial_b) * 100.0 if initial_b > 0 else 0)
        
    return {
        "profit": total_profit,
        "limit_hits": total_limit_hits,
        "max_dd_overall": max(session_drawdowns),
        "avg_dd": sum(session_drawdowns) / len(session_drawdowns)
    }

print("=== TESTING BASE BET & GROWTH FACTOR COMBINATIONS ACROSS ALL 13 SESSIONS ===\n")
print(f"{'Config Description':<40} | {'Total Profit':<14} | {'Table Limit Hits':<18} | {'Max DD (%)':<12} | {'Avg DD (%)'}")
print("-" * 95)

# Test 1: Original v10.4 (base 1k-4k, growth 2.2-2.5, sniper 1.6)
res_orig = simulate_strategy(lambda b: 1000 + ((max(500000, min(b, 6500000)) - 500000) / 6000000) * 3000, 2.35, 1.6)
print(f"{'Original v10.4 (Base 1-4k, Growth 2.35, Sniper 1.6)':<40} | {res_orig['profit']:>14,.0f} | {res_orig['limit_hits']:>18d} | {res_orig['max_dd_overall']:>10.1f}% | {res_orig['avg_dd']:>8.1f}%")

# Test 2: Safe Pure TBB (Base 1-4k, No sniperMult=1.0, Growth 2.05)
res_safe = simulate_strategy(lambda b: 1000 + ((max(500000, min(b, 6500000)) - 500000) / 6000000) * 3000, 2.05, 1.0)
print(f"{'Pure TBB Recovery (Base 1-4k, Growth 2.05, Sniper 1.0)':<40} | {res_safe['profit']:>14,.0f} | {res_safe['limit_hits']:>18d} | {res_safe['max_dd_overall']:>10.1f}% | {res_safe['avg_dd']:>8.1f}%")

# Test 3: Moderate Sniper (Base 1.5k-5k, Growth 2.1, Sniper 1.25)
res_mod = simulate_strategy(lambda b: 1500 + ((max(500000, min(b, 6500000)) - 500000) / 6000000) * 3500, 2.10, 1.25)
print(f"{'Optimized V12 (Base 1.5-5k, Growth 2.10, Sniper 1.25)':<40} | {res_mod['profit']:>14,.0f} | {res_mod['limit_hits']:>18d} | {res_mod['max_dd_overall']:>10.1f}% | {res_mod['avg_dd']:>8.1f}%")

# Test 4: Dynamic Ceiling (Base 2k-6k, Growth 2.05, Sniper 1.15)
res_dyn = simulate_strategy(lambda b: 2000 + ((max(500000, min(b, 6500000)) - 500000) / 6000000) * 4000, 2.05, 1.15)
print(f"{'Dynamic V12 High-Yield (Base 2-6k, Growth 2.05, Sn 1.15)':<40} | {res_dyn['profit']:>14,.0f} | {res_dyn['limit_hits']:>18d} | {res_dyn['max_dd_overall']:>10.1f}% | {res_dyn['avg_dd']:>8.1f}%")

# Test 5: What ruined the user in v11 (Base 26k, Growth 2.2, Sniper 1.6)
res_v11 = simulate_strategy(lambda b: max(1000, b * 0.006), 2.2, 1.6)
print(f"{'Flawed v11 (Base 0.6% [26k], Growth 2.2, Sn 1.6)':<40} | {res_v11['profit']:>14,.0f} | {res_v11['limit_hits']:>18d} | {res_v11['max_dd_overall']:>10.1f}% | {res_v11['avg_dd']:>8.1f}%")
