import json
import glob
import os
import math
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Load all 13 sessions
log_dir = r"D:\Vibe\matreshka-quantum\log storage"
all_files = sorted(glob.glob(os.path.join(log_dir, "*.json")))
new_file = r"d:\Downloads\matreshka_quantum_v11_2026-11-08.json"
all_files.append(new_file)

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

print(f"Loaded {len(sessions)} sessions for benchmarking.")

# 1. EXACT V10.4 IMPLEMENTATION
def run_v10_4(outcomes, initial_b):
    bal = float(initial_b)
    cdt = 0.0
    step = 1
    history = []
    wins = 0
    losses = 0
    peak = bal
    max_dd = 0.0
    limit_hits = 0
    
    # Engine params scaling
    min_b = 500000.0
    max_b = 6500000.0
    clamped = max(min_b, min(bal, max_b))
    ratio = (clamped - min_b) / (max_b - min_b)
    base_bet = 1000.0 + ratio * (4000.0 - 1000.0)
    growth = 2.2 + ratio * (2.5 - 2.2)
    sniper_mult = 1.6
    
    for out in outcomes:
        # Prediction
        non_zero = [h for h in history if h['outcome'] != 'ZERO']
        rec = 'RED'
        if len(history) == 0:
            rec = 'RED'
        elif len(non_zero) >= 4 and non_zero[-1]['outcome'] == non_zero[-3]['outcome'] and non_zero[-2]['outcome'] == non_zero[-4]['outcome'] and non_zero[-1]['outcome'] != non_zero[-2]['outcome']:
            rec = 'BLACK' if non_zero[-1]['outcome'] == 'RED' else 'RED'
        elif len(non_zero) >= 4 and non_zero[-1]['outcome'] == non_zero[-2]['outcome'] == non_zero[-3]['outcome'] and non_zero[-4]['outcome'] != non_zero[-1]['outcome']:
            rec = 'BLACK' if non_zero[-1]['outcome'] == 'RED' else 'RED'
        elif len(non_zero) >= 2:
            L1 = non_zero[-1]['outcome']
            L2 = non_zero[-2]['outcome']
            if L1 == L2:
                rec = 'BLACK' if L1 == 'RED' else 'RED'
            else:
                # Zebra momentum
                nz6 = non_zero[-6:]
                alt = sum(1 for i in range(1, len(nz6)) if nz6[i]['outcome'] != nz6[i-1]['outcome'])
                alt_rate = alt / max(1, len(nz6) - 1)
                rec = L1 if alt_rate < 0.80 else ('BLACK' if L1 == 'RED' else 'RED')
        else:
            rec = non_zero[-1]['outcome'] if len(non_zero) > 0 else 'RED'
            
        # Bet
        if cdt <= 0:
            bet = round(base_bet)
        else:
            tbb = round((cdt + base_bet) / 0.98)
            geom = round(base_bet * (growth ** (step - 1)))
            if cdt > base_bet * 2 and step >= 2:
                bet = max(round(tbb * sniper_mult), geom)
            else:
                bet = max(tbb, geom)
                
        if bet >= 1000000.0:
            bet = 1000000.0
            limit_hits += 1
            
        if bet > bal:
            bet = bal
            
        # Outcome
        if out == 'ZERO':
            losses += 1
            bal -= bet
            cdt += bet
            # v10.4 zero does not increase step
        elif out == rec:
            wins += 1
            pnl = bet * 0.98
            bal += pnl
            cdt = max(0.0, cdt - pnl)
            if cdt < 10.0:
                cdt = 0.0
                step = 1
        else:
            losses += 1
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
            
    return {
        "final_profit": bal - initial_b,
        "max_dd": max_dd,
        "max_dd_pct": (max_dd / initial_b) * 100.0 if initial_b > 0 else 0,
        "wins": wins,
        "losses": losses,
        "winrate": (wins / len(outcomes) * 100.0) if outcomes else 0,
        "limit_hits": limit_hits,
        "ruined": bal <= 0
    }

print("\n--- BENCHMARK 1: EXACT REPLAY OF V10.4 ACROSS ALL 13 SESSIONS ---")
print(f"{'Session Name':<40} | {'Initial (₽)':<12} | {'Profit v10.4':<14} | {'MaxDD (%)':<10} | {'Winrate':<8} | {'Status'}")
print("-" * 98)

tot_p = 0
tot_dd = 0
tot_ruins = 0

for sname, sdata in sessions.items():
    res = run_v10_4(sdata["outcomes"], sdata["initial"])
    tot_p += res["final_profit"]
    if res["ruined"]:
        tot_ruins += 1
    status = "RUINED" if res["ruined"] else f"Limit x{res['limit_hits']}" if res['limit_hits'] > 0 else "OK"
    print(f"{sname:<40} | {sdata['initial']:>12,.0f} | {res['final_profit']:>14,.0f} | {res['max_dd_pct']:>8.1f}% | {res['winrate']:>6.1f}% | {status}")

print("-" * 98)
print(f"TOTAL V10.4 PROFIT: {tot_p:,.2f} RUB | Total Ruins: {tot_ruins}/13 sessions\n")
