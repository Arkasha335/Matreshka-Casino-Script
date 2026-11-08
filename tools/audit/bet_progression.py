import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def calculate_bet(cdt, step, mode, base_bet, growth_factor, sniper_mult, bankroll):
    if cdt <= 0:
        return round(base_bet)
    tbb = round((cdt + base_bet) / 0.98)
    geom = round(base_bet * (growth_factor ** (step - 1)))
    if cdt > base_bet * 2 and step >= 2:
        sniper_bet = round(tbb * sniper_mult)
        bet = max(sniper_bet, geom)
    else:
        bet = max(tbb, geom)
    return max(base_bet, min(bet, 1000000, bankroll))

for initial_bankroll, base_b in [(1000000, 1000), (6500000, 4000)]:
    print(f"\n================================================================================")
    print(f"Progression of bets on consecutive losses (Initial Bankroll = {initial_bankroll:,} RUB, Base Bet = {base_b:,} RUB):")
    print(f"{'Step':<5} | {'Bet (RUB)':<14} | {'Cumulative Loss (CDT)':<22} | {'Remaining Bankroll':<18} | {'% Bet of Initial'}")
    print("-" * 80)

    cur_bankroll = initial_bankroll
    cdt = 0
    growth_factor = 2.2 if initial_bankroll == 1000000 else 2.5
    sniper_mult = 1.6

    for step in range(1, 15):
        bet = calculate_bet(cdt, step, 'ZEBRA', base_b, growth_factor, sniper_mult, cur_bankroll)
        pct = (bet / initial_bankroll) * 100
        print(f"{step:<5} | {bet:>14,d} | {cdt:>22,d} | {cur_bankroll:>18,d} | {pct:>15.2f}%")
        cur_bankroll -= bet
        cdt += bet
        if cur_bankroll <= 0:
            print(f"  [CRITICAL] BANKROLL COMPLETELY WIPED OUT AT STEP {step}! (Consecutive losses: {step})")
            break
        if bet >= 1000000:
            print(f"  [ALERT] TABLE LIMIT (1,000,000 RUB) HIT AT STEP {step}!")
            break
