import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"d:\Downloads\matreshka_quantum_v11_2026-11-08.json", "r", encoding="utf-8") as f:
    data = json.load(f)

meta = data.get("metadata", {})
logs = data.get("logs", [])

print("=== USER SESSION AUDIT (2026-11-08) ===")
print(f"Initial Bankroll: {meta.get('initialBankroll'):,} RUB")
print(f"Final Balance:    {meta.get('currentBankroll'):,.2f} RUB")
print(f"Total Profit:     {meta.get('totalProfit'):,.2f} RUB")
print(f"Max Drawdown:     {meta.get('maxDrawdown'):,.2f} RUB")
print(f"Total Spins:      {len(logs)}")
print(f"Winrate:          {meta.get('winRate'):.1f}%\n")

print(f"{'#':<3} | {'Outcome':<7} | {'Rec':<7} | {'Bet (RUB)':<10} | {'Step':<5} | {'Balance':<12} | {'Win':<5} | {'ZeroFreeze':<10} | {'Time (ms)'}")
print("-" * 85)

for i, log in enumerate(logs):
    out = log.get("input_result")
    rec = log.get("recommended_action")
    bet = log.get("current_bet", 0)
    step = log.get("current_step")
    bal = log.get("current_balance")
    is_win = log.get("is_win")
    zf = log.get("is_zero_freeze")
    t = log.get("time_since_last_spin")
    print(f"{i+1:<3} | {out:<7} | {rec:<7} | {bet:>10,d} | {step:<5} | {bal:>12,.0f} | {str(is_win):<5} | {str(zf):<10} | {t:>8d}")
