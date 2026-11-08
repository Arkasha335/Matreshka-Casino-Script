def compute_optimal_ladder(bankroll, limit=1_000_000, tax=0.02, desired_min_steps=9):
    # Determine maximum number of steps allowed by bankroll and limit
    # For any N steps, total cost is ~ 2 * limit (if terminal is limit)
    # If bankroll < 2,000,000, max terminal step cannot be limit, it is bounded by bankroll!
    
    # We want:
    # sum(bets) <= bankroll
    # last_bet <= limit
    # bet_k = (cdt_{k-1} + profit_k) / (1 - tax)
    
    # Let's test target step count N in [11, 10, 9, 8, 7]
    # For a given N:
    # The multiplier ratio r = (1 + 1/(1-tax)) ~ 2.0204
    # B_k ~ B1 * r^(k-1)
    # Sum ~ B1 * (r^N - 1) / (r - 1)
    # We want Sum <= bankroll AND B_N <= limit.
    
    results = {}
    for n in [11, 10, 9, 8, 7]:
        # Binary search for max B0 such that Sum <= bankroll and B_N <= limit
        low = 100
        high = 50_000
        best_b0 = None
        best_bets = None
        for _ in range(50):
            mid = (low + high) / 2
            b0 = mid
            bets = [b0]
            cdt = b0
            valid = True
            for step in range(2, n + 1):
                tbb = (cdt + b0) / (1 - tax)
                bets.append(tbb)
                cdt += tbb
                if tbb > limit or cdt > bankroll:
                    valid = False
                    break
            if valid:
                best_b0 = mid
                best_bets = bets
                low = mid
            else:
                high = mid
        if best_b0 is not None:
            results[n] = (best_b0, best_bets, sum(best_bets))
    return results

print("Optimal Ladders for various bankrolls:")
for bank in [1_000_000, 2_000_000, 3_800_000, 5_000_000]:
    print(f"\n================ Bankroll = {bank:,} RUB ================")
    ladders = compute_optimal_ladder(bank)
    for n, (b0, bets, total) in sorted(ladders.items(), reverse=True):
        print(f"N = {n:2d} steps: Max B0 = {b0:6.1f} RUB | Total Cost = {total:9,.0f} RUB | Terminal Bet = {bets[-1]:7,.0f} RUB")
