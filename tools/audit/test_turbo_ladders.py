def test_turbo_ladder(b0, s2_boost, s3_boost, limit=1_000_000, tax=0.02):
    cdt = b0
    bets = [b0]
    for step in range(2, 10):
        tbb = (cdt + b0) / (1 - tax)
        if step == 2:
            bet = round(tbb * s2_boost)
        elif step == 3:
            bet = round(tbb * s3_boost)
        else:
            bet = round(tbb)
        bets.append(bet)
        cdt += bet
    return bets

for b0 in [3565, 3400, 3300, 3200, 3100, 3000]:
    for s2 in [1.00, 1.05, 1.10]:
        bets = test_turbo_ladder(b0, s2, 1.00)
        exceeds = any(b > 1_000_000 for b in bets)
        if not exceeds:
            print(f"B0={b0}, S2={s2:.2f} -> Step 7: {bets[6]:7d} | Step 8: {bets[7]:7d} | Step 9: {bets[8]:7d} | Total: {sum(bets):8d}")
            break
