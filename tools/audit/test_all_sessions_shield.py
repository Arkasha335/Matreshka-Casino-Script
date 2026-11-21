import glob, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions
from parity_ts_vs_python import exact_bet_1m, calc_net_win
from engine_mirror import PrngDetectorMirror

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

def run_portfolio_backtest(deep_step_threshold=5, enable_shield=True):
    total_profit = 0
    win_sessions = 0
    total_spins = 0
    total_wins = 0
    resets = 0
    max_portfolio_dd = 0
    
    for s in sessions:
        outs = s['outcomes']
        bankroll = 7500000
        start_bank = bankroll
        cdt = 0
        step = 1
        history = []
        
        for o in outs:
            rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(history)
            
            if enable_shield and step >= deep_step_threshold:
                nonZero = [h['outcome'] for h in history if h['outcome'] != 'ZERO']
                if nonZero:
                    curC = nonZero[-1]
                    stk = 1
                    for k in range(len(nonZero)-2, -1, -1):
                        if nonZero[k] == curC: stk += 1
                        else: break
                    if stk >= 2:
                        rec = curC
            
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
                resets += 1
                
            bankroll += net_profit
            total_spins += 1
            if is_win: total_wins += 1
            
            history.append({
                'outcome': o,
                'betAmount': bet,
                'betColor': rec,
                'isWin': is_win,
                'netProfit': net_profit
            })
            
        pnl = bankroll - start_bank
        total_profit += pnl
        if pnl > 0: win_sessions += 1
        
    return {
        'profit': total_profit,
        'win_sessions': win_sessions,
        'total_sessions': len(sessions),
        'wr': total_wins / total_spins * 100,
        'resets': resets
    }

print("Comparing Portfolio across all 50 sessions:")
res_baseline = run_portfolio_backtest(enable_shield=False)
print(f"Baseline (v16.1): Profit = {res_baseline['profit']:+12,.0f} ₽ | Win Sess: {res_baseline['win_sessions']}/{res_baseline['total_sessions']} | Resets: {res_baseline['resets']:2d} | WR = {res_baseline['wr']:.2f}%")

for thresh in [4, 5, 6]:
    res_shield = run_portfolio_backtest(deep_step_threshold=thresh, enable_shield=True)
    print(f"Shield Step {thresh:2d}:  Profit = {res_shield['profit']:+12,.0f} ₽ | Win Sess: {res_shield['win_sessions']}/{res_shield['total_sessions']} | Resets: {res_shield['resets']:2d} | WR = {res_shield['wr']:.2f}%")
