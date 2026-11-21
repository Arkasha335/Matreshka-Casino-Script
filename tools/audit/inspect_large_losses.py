import csv

with open('bot/logs/session_20261119_223110.csv', 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

large_bets = [r for r in rows if float(r['bet_amount']) >= 50000]
print(f"Total bets >= 50k: {len(large_bets)}")
for r in large_bets:
    print(f"Spin {r['spin']:>3s} | Step {r['step']} | Bet: {float(r['bet_amount']):>10,.0f} on {r['bet_color']:>5s} | Out: {r['outcome']:>5s} | Win: {r['is_win']:>4s} | Bank: {float(r['bankroll']):>10,.0f} | CDT: {float(r['cdt']):>10,.0f}")
