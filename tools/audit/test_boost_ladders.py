def test_boost_ladder(b0, s2_boost, s3_boost, limit=1_000_000, tax=0.02):
    cdt = b0
    bets = [b0]
    for step in range(2, 11):
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

print("Testing impact of Step 2 and Step 3 boosts on the 10-step ladder:")
configs = [
    (1765, 1.00, 1.00),
    (1765, 1.05, 1.00),
    (1700, 1.08, 1.04),
    (1650, 1.10, 1.05),
    (1600, 1.12, 1.06),
]

for b0, s2, s3 in configs:
    bets = test_boost_ladder(b0, s2, s3)
    exceeds = any(b > 1_000_000 for b in bets)
    print(f"B0={b0}, S2={s2:.2f}, S3={s3:.2f} -> Step 8: {bets[7]:7d} | Step 9: {bets[8]:7d} | Step 10: {bets[9]:7d} | Exceeds: {exceeds} | Total: {sum(bets):8d}")
