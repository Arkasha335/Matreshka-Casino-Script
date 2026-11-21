import glob, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions
from parity_ts_vs_python import exact_bet_1m, calc_net_win
from engine_mirror import PrngDetectorMirror

sessions = load_all_unique_sessions()
user_session = [s for s in sessions if 'session_20261119_223110' in s['file']][0]

def simulate_with_rule(follow_streak_on_deep_steps=True, deep_step_threshold=4):
    bankroll = 8612784
    cdt = 0
    step = 1
    history = []
    
    total_bets = 0
    wins = 0
    losses = 0
    max_bet = 0
    max_step = 1
    max_drawdown = 0
    start_bank = bankroll
    
    for idx, o in enumerate(user_session['outcomes']):
        # Standard prediction
        rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(history)
        
        # Deep step trend-alignment rule
        if follow_streak_on_deep_steps and step >= deep_step_threshold:
            nonZero = [h['outcome'] for h in history if h['outcome'] != 'ZERO']
            if nonZero:
                curC = nonZero[-1]
                stk = 1
                for k in range(len(nonZero)-2, -1, -1):
                    if nonZero[k] == curC: stk += 1
                    else: break
                if stk >= 2:
                    # Align with streak!
                    rec = curC
                    state = f'DEEP_STEP_STREAK_SHIELD (Step {step}, Streak {stk})'
        
        # Calculate bet
        target_steps = 10
        limit = 1000000
        base_bet = 1400
        
        if cdt <= 0 or step <= 1:
            bet = base_bet
        elif step > target_steps:
            bet = base_bet
        else:
            rem = max(1, target_steps - step + 1)
            min_tbb = math.ceil(((cdt + base_bet) * 100) / 98)
            while calc_net_win(min_tbb) < cdt + base_bet: min_tbb += 1
            if rem == 1:
                cap = min(limit, bankroll)
                bet = max(1000, min(cap, min_tbb))
            else:
                pb = 1400 if step == 2 else history[-1]['betAmount']
                growth = math.pow(limit / pb, 1.0 / rem) if rem > 0 else 2.0
                growth = max(1.05, min(2.5, growth))
                bet = max(min_tbb, round(pb * growth))
                bet = min(limit, min(bankroll, bet))
                
        bet = min(bet, bankroll)
        max_bet = max(max_bet, bet)
        max_step = max(max_step, step)
        
        is_win = (rec == o)
        if o == 'ZERO':
            is_win = False
            net_profit = -bet
            cdt += bet
            step += 1
        elif is_win:
            net_profit = calc_net_win(bet)
            cdt = max(0, cdt - net_profit)
            if cdt == 0: step = 1
        else:
            net_profit = -bet
            cdt += bet
            step += 1
            
        if not is_win and (bet >= limit or step > target_steps):
            cdt = 0
            step = 1
            
        bankroll += net_profit
        max_drawdown = max(max_drawdown, start_bank - bankroll)
        total_bets += 1
        if is_win: wins += 1
        else: losses += 1
        
        history.append({
            'outcome': o,
            'betAmount': bet,
            'betColor': rec,
            'isWin': is_win,
            'netProfit': net_profit
        })
        
    return {
        'wr': wins / total_bets * 100,
        'final_bank': bankroll,
        'pnl': bankroll - start_bank,
        'max_bet': max_bet,
        'max_step': max_step,
        'max_dd': max_drawdown
    }

print("Simulating User Session with Deep Step Streak Shield...")
for thresh in [3, 4, 5, 6]:
    res = simulate_with_rule(follow_streak_on_deep_steps=True, deep_step_threshold=thresh)
    print(f"Threshold = Step {thresh:2d} | PnL = {res['pnl']:+10,.0f} ₽ | Max Bet = {res['max_bet']:10,.0f} ₽ | Max Step = {res['max_step']:2d} | Max DD = {res['max_dd']:10,.0f} ₽ | WR = {res['wr']:.2f}%")

res_none = simulate_with_rule(follow_streak_on_deep_steps=False)
print(f"No Streak Shield   | PnL = {res_none['pnl']:+10,.0f} ₽ | Max Bet = {res_none['max_bet']:10,.0f} ₽ | Max Step = {res_none['max_step']:2d} | Max DD = {res_none['max_dd']:10,.0f} ₽ | WR = {res_none['wr']:.2f}%")
