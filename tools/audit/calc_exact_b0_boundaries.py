def find_max_b0(target_steps, limit=1_000_000, tax=0.02):
    # Binary search for max b0
    low = 100
    high = 100_000
    best_b0 = low
    for _ in range(50):
        mid = (low + high) / 2
        # simulate ladder
        b0 = mid
        cdt = b0
        steps = 1
        last_bet = b0
        valid = True
        while steps < target_steps:
            tbb = (cdt + b0) / (1 - tax)
            steps += 1
            last_bet = tbb
            cdt += tbb
            if last_bet > limit:
                valid = False
                break
        if valid and last_bet <= limit:
            best_b0 = mid
            low = mid
        else:
            high = mid
    return round(best_b0), round(cdt)

print("Exact Maximum B0 for Pure TBB (mult=1.0) to fit exactly N steps under 1,000,000:")
for n in [7, 8, 9, 10, 11]:
    max_b, bank = find_max_b0(n)
    print(f"N = {n:2d} steps: Max B0 = {max_b:6d} RUB | Total Bankroll Required = {bank:9d} RUB")
