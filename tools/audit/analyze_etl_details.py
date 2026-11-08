import json
import numpy as np

with open(r"D:\Projects\MTCasinoScript\tools\audit\normalized_spins.json", "r", encoding="utf-8") as f:
    spins = json.load(f)

print(f"Total spins loaded: {len(spins)}")

delta_mismatches = []
time_deltas = []
bets = []
balances = []

for i, s in enumerate(spins):
    bets.append(s["bet"])
    balances.append(s["balance"])
    if s["time_since_last_spin_ms"] > 0:
        time_deltas.append(s["time_since_last_spin_ms"])
    
    if s["actual_next_balance_delta"] is not None and not s["delta_matches_expected"]:
        delta_mismatches.append({
            "idx": i,
            "session": s["session_id"],
            "spin_idx": s["spin_idx"],
            "bet": s["bet"],
            "action": s["recommended_action"],
            "outcome": s["outcome"],
            "expected_delta": s["expected_delta"],
            "actual_delta": s["actual_next_balance_delta"],
            "diff": s["actual_next_balance_delta"] - s["expected_delta"]
        })

print(f"Delta mismatches count: {len(delta_mismatches)}")
if delta_mismatches:
    print("First 5 mismatches:")
    for m in delta_mismatches[:5]:
        print(" ", m)

# Time metrics
time_arr = np.array(time_deltas) / 1000.0  # seconds
print("\n--- Time Metrics between spins (seconds) ---")
print(f"Count: {len(time_arr)}")
print(f"Mean: {np.mean(time_arr):.2f}s")
print(f"Median: {np.median(time_arr):.2f}s")
print(f"Min: {np.min(time_arr):.2f}s")
print(f"Max: {np.max(time_arr):.2f}s")
print(f"Standard deviation: {np.std(time_arr):.2f}s")
print(f"Percentiles (25%, 75%, 90%, 99%): {np.percentile(time_arr, [25, 75, 90, 99])}")

# Bet sizes
bet_arr = np.array(bets)
print("\n--- Bet Metrics (Rubles) ---")
print(f"Min bet: {np.min(bet_arr)}")
print(f"Max bet: {np.max(bet_arr):,.2f}")
print(f"Mean bet: {np.mean(bet_arr):,.2f}")
print(f"Median bet: {np.median(bet_arr):,.2f}")
print(f"Top 10 largest bets:")
for b in sorted(bet_arr, reverse=True)[:10]:
    print(f"  {b:,.2f} ₽")
