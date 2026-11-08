import json
import math
import sys
import numpy as np

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Projects\MTCasinoScript\tools\audit\normalized_spins.json", "r", encoding="utf-8") as f:
    spins = json.load(f)

# Group by session
sessions = {}
for s in spins:
    sid = s["session_id"]
    if sid not in sessions:
        sessions[sid] = []
    sessions[sid].append(s)

print("================================================================================")
print("     BACKTESTING NEW QUANTUM SURGE ENGINE ON 984 REAL HISTORICAL SPINS          ")
print("================================================================================\n")

def run_session_backtest(s_list, profile='HIGH_ROLLER_MAX', stop_loss_pct=0.15, take_profit_pct=0.25, trailing_stop_pct=0.04, zero_freeze_spins=3):
    initial_b = s_list[0]["balance"]
    bal = float(initial_b)
    peak = bal
    max_dd = 0.0
    cdt = 0.0
    step = 1
    surge_step = 0
    freeze_rem = 0
    
    # Base bet
    if profile == 'HIGH_ROLLER_MAX':
        base_b = max(1000.0, round((initial_b * 0.012) / 500) * 500)
        surge_mults = [1.0, 1.8, 3.2, 5.5]
    elif profile == 'BALANCED_QUANT':
        base_b = max(1000.0, round((initial_b * 0.006) / 500) * 500)
        surge_mults = [1.0, 1.5, 2.2]
    else:
        base_b = max(1000.0, round((initial_b * 0.003) / 500) * 500)
        surge_mults = [1.0]

    history = []
    wins = 0
    losses = 0
    zeros = 0
    spins_skipped = 0
    halted = False
    halt_reason = "NONE"
    
    for s in s_list:
        outcome = s["outcome"]
        
        # Risk check
        curr_dd = peak - bal
        if curr_dd >= initial_b * stop_loss_pct:
            halted = True
            halt_reason = "STOP_LOSS"
            break
            
        cur_profit = bal - initial_b
        peak_profit = peak - initial_b
        if peak_profit >= initial_b * take_profit_pct:
            if (peak_profit - cur_profit) >= initial_b * trailing_stop_pct:
                halted = True
                halt_reason = "TAKE_PROFIT_LOCK"
                break
                
        # Zero freeze check
        if freeze_rem > 0:
            freeze_rem -= 1
            spins_skipped += 1
            history.append(outcome)
            if outcome == 'ZERO':
                freeze_rem = zero_freeze_spins
            continue
            
        # Predict color using pattern logic
        if len(history) < 2:
            pred = 'RED'
        else:
            # Alternation check
            non_z = [o for o in history if o != 'ZERO']
            if len(non_z) >= 3:
                transitions = sum(1 for i in range(1, len(non_z[-15:])) if non_z[-15:][i] != non_z[-15:][i-1])
                alt_rate = transitions / max(1, len(non_z[-15:]) - 1)
                opp_L1 = 'BLACK' if non_z[-1] == 'RED' else 'RED'
                if alt_rate >= 0.70:
                    pred = opp_L1
                else:
                    pred = non_z[-1]
            else:
                pred = history[-1] if history[-1] != 'ZERO' else 'RED'
                
        # Bet calculation
        if cdt > 0:
            surge_step = 0
            if step <= 4:
                tbb = round((cdt + base_b) / 0.98)
                geom = round(base_b * (2.1 ** (step - 1)))
                bet = max(tbb, geom)
            else:
                # Soft amortization
                bet = base_b + round(cdt / 6)
        else:
            step = 1
            if surge_step > 0 and surge_step < len(surge_mults):
                bet = round(base_b * surge_mults[surge_step])
            else:
                bet = base_b
                surge_step = 0
                
        # Safety bound: max 10% single bet
        max_limit = min(1000000.0, bal * 0.10)
        bet = min(bet, max_limit)
        bet = max(1000.0, bet)
        
        # Outcome resolution
        history.append(outcome)
        if outcome == 'ZERO':
            zeros += 1
            losses += 1
            bal -= bet
            cdt += bet
            step += 1
            surge_step = 0
            freeze_rem = zero_freeze_spins
        elif outcome == pred:
            wins += 1
            pnl = bet * 0.98
            bal += pnl
            cdt = max(0.0, cdt - pnl)
            if cdt < 50.0:
                cdt = 0.0
                step = 1
                surge_step += 1
            else:
                surge_step = 0
        else:
            losses += 1
            bal -= bet
            cdt += bet
            step += 1
            surge_step = 0
            
        if bal > peak:
            peak = bal
        dd = peak - bal
        if dd > max_dd:
            max_dd = dd
            
    final_profit = bal - initial_b
    return {
        "initial": initial_b,
        "final": bal,
        "profit": final_profit,
        "max_dd": max_dd,
        "max_dd_pct": (max_dd / initial_b) * 100.0,
        "wins": wins,
        "losses": losses,
        "zeros": zeros,
        "skipped": spins_skipped,
        "halted": halted,
        "halt_reason": halt_reason
    }

for prof in ['HIGH_ROLLER_MAX', 'BALANCED_QUANT']:
    print(f"--- Strategy Profile: {prof} ---")
    print(f"{'Session ID':<30} | {'Start Bank':<12} | {'New Profit':<14} | {'Old Profit':<14} | {'MaxDD (%)':<10} | {'Status'}")
    print("-" * 92)
    
    tot_new_profit = 0
    tot_old_profit = 0
    
    for sid, s_list in sessions.items():
        res = run_session_backtest(s_list, profile=prof)
        old_profit = s_list[-1]["balance"] - s_list[0]["balance"] + (s_list[-1]["expected_delta"] if s_list[-1]["actual_next_balance_delta"] is None else 0)
        tot_new_profit += res["profit"]
        tot_old_profit += old_profit
        
        status = res["halt_reason"] if res["halted"] else "FINISHED"
        print(f"{sid:<30} | {res['initial']:>12,.0f} | {res['profit']:>14,.0f} | {old_profit:>14,.0f} | {res['max_dd_pct']:>8.1f}% | {status}")
        
    print("-" * 92)
    print(f"{'TOTAL ACROSS ALL SESSIONS':<30} | {'-':<12} | {tot_new_profit:>14,.0f} | {tot_old_profit:>14,.0f} | {'-':<10} | -\n")
