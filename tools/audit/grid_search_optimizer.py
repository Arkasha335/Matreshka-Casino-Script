import json
import glob
import os
import math
import sys
import numpy as np

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 1. Load all 13 historical sessions
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

print(f"Loaded {len(sessions)} sessions ({sum(len(s['outcomes']) for s in sessions.values())} total spins).")

# V10.4 MPD & Apex Matrix Predictor
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
    
    # Apex streak in last 20
    w20 = non_zero[-20:]
    max_streak_red = 0
    max_streak_black = 0
    c_s = 0
    c_c = None
    red_count = 0
    black_count = 0
    for h in w20:
        if h['outcome'] == 'RED': red_count += 1
        if h['outcome'] == 'BLACK': black_count += 1
        if h['outcome'] == c_c:
            c_s += 1
        else:
            c_c = h['outcome']
            c_s = 1
        if c_c == 'RED' and c_s > max_streak_red: max_streak_red = c_s
        if c_c == 'BLACK' and c_s > max_streak_black: max_streak_black = c_s
        
    alpha = 'NEUTRAL'
    omega = 'NEUTRAL'
    if len(w20) > 0:
        if red_count / len(w20) > 0.55:
            alpha = 'RED'
            omega = 'BLACK'
        elif black_count / len(w20) > 0.55:
            alpha = 'BLACK'
            omega = 'RED'
            
    active_streak = 0
    active_col = non_zero[-1]['outcome']
    for i in range(len(non_zero)-1, -1, -1):
        if non_zero[i]['outcome'] == active_col:
            active_streak += 1
        else:
            break
            
    curr_max = max_streak_red if active_col == 'RED' else max_streak_black
    if active_streak >= curr_max and curr_max > 0:
        return ('BLACK' if active_col == 'RED' else 'RED'), 90, 'ОТСКОК ОТ ПОТОЛКА'
    elif L1 == L2:
        if L1 == alpha and curr_max > 2:
            return L1, 75, 'АЛЬФА-ТРЕНД'
        elif L1 == omega:
            return ('BLACK' if L1 == 'RED' else 'RED'), 30, 'ОМЕГА-ЛОВУШКА'
        else:
            return ('BLACK' if L1 == 'RED' else 'RED'), 50, 'НЕЙТРАЛЬНО'
    else:
        nz6 = non_zero[-6:]
        alt = sum(1 for i in range(1, len(nz6)) if nz6[i]['outcome'] != nz6[i-1]['outcome'])
        alt_rate = alt / max(1, len(nz6) - 1)
        rec = L1 if alt_rate < 0.80 else ('BLACK' if L1 == 'RED' else 'RED')
        return rec, 60, 'ЧЕРЕДОВАНИЕ'

# Simulator function
def run_simulation(base_bet_fn, bet_calc_fn):
    total_profit = 0
    total_limit_hits = 0
    total_ruins = 0
    sessions_won = 0
    max_drawdowns = []
    
    for sname, sdata in sessions.items():
        init_b = sdata["initial"]
        bal = float(init_b)
        peak = bal
        max_dd = 0
        cdt = 0
        step = 1
        history = []
        limit_hits = 0
        
        base_b = base_bet_fn(init_b)
        
        for out in sdata["outcomes"]:
            rec, conf, pat = get_recommendation_v10(history)
            bet = bet_calc_fn(cdt, step, base_b, bal)
            
            if bet >= 1000000:
                limit_hits += 1
                bet = 1000000
                
            if bet > bal:
                bet = bal
                
            if out == 'ZERO':
                bal -= bet
                cdt += bet
                # Zero does not increment step in v10
            elif out == rec:
                pnl = bet * 0.98
                bal += pnl
                cdt = max(0.0, cdt - pnl)
                if cdt < 10.0:
                    cdt = 0.0
                    step = 1
            else:
                bal -= bet
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
                
        pnl = bal - init_b
        total_profit += pnl
        if pnl > 0:
            sessions_won += 1
        if bal <= 0:
            total_ruins += 1
        total_limit_hits += limit_hits
        max_drawdowns.append((max_dd / init_b) * 100.0 if init_b > 0 else 0)
        
    return {
        "profit": total_profit,
        "sessions_won": sessions_won,
        "ruins": total_ruins,
        "limit_hits": total_limit_hits,
        "worst_dd": max(max_drawdowns),
        "avg_dd": sum(max_drawdowns) / len(max_drawdowns)
    }

# GRID SEARCH OVER CANDIDATE FORMULAS
results = []

# Base bet scaling approaches:
# A1: Linear 1,000 to 4,000 for 500k to 6.5M (v10.4 style)
# A2: Linear 1,500 to 5,000
# A3: Linear 2,000 to 6,000
# A4: Fraction of bankroll: 0.0007 (0.07%), 0.0008, 0.001 (0.1%), capped 1k - 5k

base_candidates = [
    ("v10_linear_1_4k", lambda b: 1000 + ((max(500000, min(b, 6500000)) - 500000) / 6000000) * 3000),
    ("opt_linear_1.5_4.5k", lambda b: 1500 + ((max(500000, min(b, 6500000)) - 500000) / 6000000) * 3000),
    ("opt_linear_2_5k", lambda b: 2000 + ((max(500000, min(b, 6500000)) - 500000) / 6000000) * 3000),
    ("opt_linear_2.5_6k", lambda b: 2500 + ((max(500000, min(b, 6500000)) - 500000) / 6000000) * 3500),
    ("opt_fraction_0.08pct", lambda b: max(1000, min(5000, round(b * 0.0008 / 100) * 100))),
]

# Bet calculation multiplier strategies:
# Strategy 1: Classical Pure TBB (Exact mathematical recovery, 0 excess multiplier)
# Strategy 2: Adaptive Tiered TBB (1.15x boost on step 2, 1.1x on step 3, pure TBB on step 4+)
# Strategy 3: Moderate Sniper (1.20x sniper, pure TBB on step 5+)
# Strategy 4: High Sniper (1.35x sniper)
# Strategy 5: Original v10.4 (1.6x sniper, growth 2.2 - 2.5)

growth_candidates = [
    # (name, sniper_mult, step_sniper_cap, geom_factor)
    ("Pure_TBB", 1.0, 0, 2.05),
    ("Adaptive_Tiered_1.15", 1.15, 3, 2.10),
    ("Adaptive_Tiered_1.20", 1.20, 4, 2.15),
    ("Adaptive_Tiered_1.25", 1.25, 4, 2.15),
    ("Moderate_Sniper_1.30", 1.30, 5, 2.20),
    ("Original_v10_Sniper_1.6", 1.60, 99, 2.35),
]

print("\n--- RUNNING PARAMETRIC GRID SEARCH ---")
for b_name, b_fn in base_candidates:
    for g_name, sn_mult, sn_cap, geom_f in growth_candidates:
        def make_calc(s_mult, s_cap, g_f):
            def calc(cdt, step, base_b, bal):
                if cdt <= 0:
                    return round(base_b)
                tbb = round((cdt + base_b) / 0.98)
                geom = round(base_b * (g_f ** (step - 1)))
                if cdt > base_b * 2 and step >= 2 and step <= s_cap and s_mult > 1.0:
                    bet = max(round(tbb * s_mult), geom)
                else:
                    bet = max(tbb, geom)
                return max(round(base_b), min(bet, 1000000, round(bal)))
            return calc
            
        res = run_simulation(b_fn, make_calc(sn_mult, sn_cap, geom_f))
        results.append({
            "base_name": b_name,
            "growth_name": g_name,
            "profit": res["profit"],
            "won": res["sessions_won"],
            "limit_hits": res["limit_hits"],
            "worst_dd": res["worst_dd"],
            "avg_dd": res["avg_dd"]
        })

# Sort by profit descending, filtering for 0 ruins and minimal limit hits
results.sort(key=lambda r: (r["limit_hits"], -r["profit"]))

print(f"\n{'Rank':<4} | {'Base Strategy':<22} | {'Growth Strategy':<22} | {'Total Profit':<14} | {'Won/13':<8} | {'Limit Hits':<12} | {'Worst DD':<10}")
print("-" * 105)

for rank, r in enumerate(results[:15], 1):
    print(f"{rank:<4} | {r['base_name']:<22} | {r['growth_name']:<22} | {r['profit']:>14,.0f} | {r['won']:>4d}/13  | {r['limit_hits']:>12d} | {r['worst_dd']:>8.1f}%")
