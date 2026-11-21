import glob, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions
from parity_ts_vs_python import exact_bet_1m, calc_net_win

sessions = load_all_unique_sessions()
user_session = [s for s in sessions if 'session_20261119_223110' in s['file']][0]
print(f"Loaded user session: {len(user_session['outcomes'])} spins")

# Compare terminal bet logic:
# Old logic: finalTerminal = cap if cdt >= cap * 0.30 else min(minTbb, cap)
# New logic: finalTerminal = min(minTbb, cap)

def simulate_session(predictor_fn, use_safe_terminal=False):
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
    lowest_bank = bankroll
    
    for o in user_session['outcomes']:
        # 1. Prediction
        rec, conf, state = predictor_fn(history)
        
        # 2. Bet calculation (APEX IDEAL, targetSteps=8 for ZEBRA, 10 for DANGER)
        # Using exact_bet_1m with safe terminal option
        eff_mode = 'ZEBRA' if cdt > 0 else 'ZEBRA'
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
            while calc_net_win(min_tbb) < cdt + base_bet:
                min_tbb += 1
                
            if rem == 1:
                cap = min(limit, bankroll)
                if use_safe_terminal:
                    bet = max(1000, min(cap, min_tbb))
                else:
                    final_terminal = min_tbb if cdt < cap * 0.30 else cap
                    bet = max(1000, min(cap, final_terminal))
            else:
                # normal geometric growth
                pb = 1400 if step == 2 else history[-1]['betAmount']
                growth = math.pow(limit / pb, 1.0 / rem) if rem > 0 else 2.0
                growth = max(1.05, min(2.5, growth))
                bet = max(min_tbb, round(pb * growth))
                bet = min(limit, min(bankroll, bet))
                
        bet = min(bet, bankroll)
        max_bet = max(max_bet, bet)
        max_step = max(max_step, step)
        
        # 3. Outcome
        is_win = (rec == o)
        if o == 'ZERO':
            is_win = False
            net_profit = -bet
            cdt += bet
            step += 1
        elif is_win:
            net_profit = calc_net_win(bet)
            cdt = max(0, cdt - net_profit)
            if cdt == 0:
                step = 1
        else:
            net_profit = -bet
            cdt += bet
            step += 1
            
        # Terminal check
        if not is_win and (bet >= limit or step > target_steps):
            cdt = 0
            step = 1
            
        bankroll += net_profit
        lowest_bank = min(lowest_bank, bankroll)
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

print("Running baseline v16.1 simulation on user test session...")
from engine_mirror import PrngDetectorMirror
res_old = simulate_session(PrngDetectorMirror.get_recommendation_and_confidence, use_safe_terminal=False)
res_safe_term = simulate_session(PrngDetectorMirror.get_recommendation_and_confidence, use_safe_terminal=True)

print(f"v16.1 Original: PnL = {res_old['pnl']:+10,.0f} ₽ | Max Bet = {res_old['max_bet']:10,.0f} ₽ | Max DD = {res_old['max_dd']:10,.0f} ₽ | WR = {res_old['wr']:.2f}%")
print(f"v16.1 SafeTerm: PnL = {res_safe_term['pnl']:+10,.0f} ₽ | Max Bet = {res_safe_term['max_bet']:10,.0f} ₽ | Max DD = {res_safe_term['max_dd']:10,.0f} ₽ | WR = {res_safe_term['wr']:.2f}%")
