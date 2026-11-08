import json
from simulate_terminal_strategies import MPDPredictor

with open(r'd:\Downloads\matreshka_session_2026-11-08.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

outcomes = [x['input_result'] for x in data['logs']]

def test_on_session(name, b0_val):
    pred = MPDPredictor()
    bank = 3806838
    cdt = 0
    step = 1
    max_step = 0
    max_bet = 0
    wins = 0
    print(f"\n=== Testing {name} on Today's Session ===")
    for i, out in enumerate(outcomes):
        rec = pred.get_recommendation()
        if step == 1:
            bet = b0_val
        else:
            bet = round((cdt + b0_val) / 0.98)
            if step >= 10:
                bet = 1_000_000
        
        max_step = max(max_step, step)
        max_bet = max(max_bet, bet)
        
        is_win = (out == rec)
        if is_win:
            net = bet * 1.98 - bet
            bank += net
            cdt = 0
            step = 1
            wins += 1
        else:
            bank -= bet
            cdt += bet
            step += 1
            
        pred.add_result(out)
        print(f"Spin {i+1:2d} | Out: {out:5s} | Rec: {rec:5s} | Win: {str(is_win):5s} | Step: {step-1 if is_win else step:2d} | Bet: {bet:7d} | Bank: {bank:10.2f}")

    print(f"\nFinal Bankroll: {bank:,.2f} RUB (Profit: {bank - 3806838:,.2f} RUB)")
    print(f"Max Step: {max_step} | Max Bet: {max_bet:,.2f} RUB | Winrate: {wins/len(outcomes)*100:.1f}%")

test_on_session("Terminal 10-Step (B0=1765)", 1765)
test_on_session("Calibrated (B0=2000)", 2000)
