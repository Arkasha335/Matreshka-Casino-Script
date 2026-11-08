import math

def analyze_b0_steps(b0, n_steps=10):
    print(f"=== B0 = {b0}, Target Steps = {n_steps} ===")
    growth_x = math.pow(1_000_000 / b0, 1.0 / (n_steps - 1))
    print(f"Growth Factor X: {growth_x:.4f}")
    cdt = 0
    bet = b0
    for s in range(1, n_steps + 1):
        if s == n_steps:
            bet = 1_000_000
        elif s > 1:
            bet = round(bet * growth_x)
        net_win_on_win = round(bet * 0.98) - cdt
        print(f"Step {s:2d} | Bet: {bet:7,d} | CDT before: {cdt:9,d} | Net on Win: {net_win_on_win:+8,d} RUB")
        cdt += bet

analyze_b0_steps(1000, 10)
print()
analyze_b0_steps(1500, 10)
print()
analyze_b0_steps(1800, 10)
print()
analyze_b0_steps(2000, 10)
print()
analyze_b0_steps(3000, 10)
print()
analyze_b0_steps(3000, 9)
print()
analyze_b0_steps(4000, 9)
