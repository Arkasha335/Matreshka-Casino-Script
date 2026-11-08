def simulate_ladder(b0, multipliers, tax=0.02):
    limit = 1_000_000
    bets = [b0]
    cdt = b0
    for i in range(1, 15):
        # target to recover cdt + b0
        tbb = (cdt + b0) / (1.0 - tax)
        # or multiplier based
        mult = multipliers(i, cdt, b0)
        bet = round(tbb * mult)
        if bet > limit:
            break
        bets.append(bet)
        cdt += bet
    return bets

print("Testing pure TBB (mult=1.0):")
for b in [1000, 1500, 2000, 2500, 3000, 3300, 4000, 5000]:
    bets = simulate_ladder(b, lambda step, cdt, b0: 1.0)
    print(f"B0 = {b:5d}: {len(bets)} steps | Bets: {bets} | Total needed: {sum(bets)}")
