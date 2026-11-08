import math

print(f"{'B0 (RUB)':<10} | {'Max Steps N':<12} | {'Exact X for N':<15} | {'CDT before final':<18} | {'Final Net Profit'}")
print("=" * 75)

for b0 in [500, 1000, 1200, 1500, 2000, 2500, 3000, 4000, 5000]:
    ratio = 1_000_000 / b0
    max_steps_float = 1 + math.log(ratio) / math.log(2.0204)
    max_n = int(math.floor(max_steps_float))
    
    # Calculate exact X for this N
    x = math.pow(ratio, 1.0 / (max_n - 1))
    
    # Calculate bets
    bets = [round(b0 * math.pow(x, k)) for k in range(max_n)]
    cdt_before_final = sum(bets[:-1])
    final_win = int(round(bets[-1] * 0.98 - cdt_before_final))
    
    print(f"{b0:<10d} | {max_n:<12d} | {x:<15.4f} | {cdt_before_final:<18,d} | {final_win:+14,d}")
