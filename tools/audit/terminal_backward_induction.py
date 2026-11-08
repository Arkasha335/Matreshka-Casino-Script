def backward_induction(n_steps, limit=1_000_000, tax=0.02):
    # If the N-th step is exactly equal to the limit L = 1,000,000
    # In pure TBB: B_k = (CDT_{k-1} + profit_k) / 0.98
    # CDT_k = CDT_{k-1} + B_k
    # If profit is constant = B0:
    # B_k = (CDT_{k-1} + B0) / 0.98
    # What B0 makes B_N = 1,000,000?
    low = 100
    high = 100_000
    for _ in range(50):
        b0 = (low + high) / 2
        cdt = b0
        bets = [b0]
        for step in range(2, n_steps + 1):
            tbb = (cdt + b0) / (1 - tax)
            bets.append(tbb)
            cdt += tbb
        if bets[-1] < limit:
            low = b0
        else:
            high = b0
    return b0, bets

print("Backward Induction: B0 that makes the N-th step exactly reach 1,000,000 RUB:")
for n in [8, 9, 10]:
    b0, bets = backward_induction(n)
    print(f"\n--- N = {n} steps ---")
    print(f"Optimal Base Bet B0 = {b0:.2f} RUB")
    print("Ladder:")
    cum = 0
    for i, b in enumerate(bets):
        cum += b
        profit_on_win = b * 0.98 - (cum - b)
        print(f"  Step {i+1:2d}: Bet = {round(b):7d} | Total Lost if miss = {round(cum):8d} | Net Profit if win = {round(profit_on_win):6d}")
