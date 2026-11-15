import json
from collections import Counter

log_path = 'bot/logs/session_20261115_200052.jsonl'
lines = [json.loads(l) for l in open(log_path, encoding='utf-8') if l.strip()]

print(f"Total spins in log: {len(lines)}")
first = lines[0]
last = lines[-1]
initial_bank = first['bankroll'] - first['net_profit']
final_bank = last['bankroll']
profit = final_bank - initial_bank

print(f"Initial Bankroll: {initial_bank:,} RUB")
print(f"Final Bankroll:   {final_bank:,} RUB")
print(f"Net Profit:       {profit:+,} RUB")

wins = sum(1 for r in lines if r['is_win'])
losses = len(lines) - wins
print(f"Wins: {wins}, Losses: {losses}, Raw WinRate: {wins/len(lines)*100:.2f}%")

zeros = sum(1 for r in lines if r['outcome'] == 'ZERO')
reds = sum(1 for r in lines if r['outcome'] == 'RED')
blacks = sum(1 for r in lines if r['outcome'] == 'BLACK')
nz = len(lines) - zeros
print(f"Outcomes: RED={reds} ({reds/len(lines)*100:.1f}%), BLACK={blacks} ({blacks/len(lines)*100:.1f}%), ZERO={zeros} ({zeros/len(lines)*100:.2f}%)")
if nz > 0:
    print(f"Non-zero WinRate: {wins/nz*100:.2f}%")

max_bet = max(r['bet_amount'] for r in lines)
max_step = max(r['step'] for r in lines)
max_cdt = max(r.get('cdt', 0) for r in lines)
print(f"Max Bet:  {max_bet:,} RUB")
print(f"Max Step: {max_step}")
print(f"Max CDT:  {max_cdt:,} RUB")

bets_1m = [r for r in lines if r['bet_amount'] >= 1_000_000]
print(f"Bets >= 1,000,000 RUB: {len(bets_1m)}")
for b in bets_1m:
    print(f"  Spin #{b['spin']}: Bet={b['bet_amount']:,} on {b['bet_color']} | Out={b['outcome']} | Win={b['is_win']} | Step={b['step']} | Bank={b['bankroll']:,}")

step_counts = Counter(r['step'] for r in lines)
print(f"\nStep distribution:")
for s, c in sorted(step_counts.items()):
    pct = c / len(lines) * 100
    print(f"  Step {s:2d}: {c:4d} spins ({pct:5.1f}%)")

# Server modes
mode_counts = Counter(r.get('server_mode', 'UNKNOWN') for r in lines)
print(f"\nModes encountered: {dict(mode_counts)}")

# Max Drawdown & Peak Bankroll
peak = initial_bank
max_dd = 0
for r in lines:
    b = r['bankroll']
    if b > peak: peak = b
    dd = peak - b
    if dd > max_dd: max_dd = dd

print(f"\nPeak Bankroll: {peak:,} RUB")
print(f"Max Drawdown:  {max_dd:,} RUB")

# Let's inspect streaks in outcomes
streak = 1
max_streak = 1
max_streak_color = None
current_color = None
for r in lines:
    o = r['outcome']
    if o == 'ZERO':
        current_color = None
        streak = 0
        continue
    if o == current_color:
        streak += 1
        if streak > max_streak:
            max_streak = streak
            max_streak_color = o
    else:
        current_color = o
        streak = 1
print(f"Max Color Streak: {max_streak} ({max_streak_color})")

# Alternation rate
nz_outs = [r['outcome'] for r in lines if r['outcome'] != 'ZERO']
alts = sum(1 for i in range(1, len(nz_outs)) if nz_outs[i] != nz_outs[i-1])
alt_rate = alts / (len(nz_outs) - 1) if len(nz_outs) > 1 else 0.5
print(f"Alternation Rate (non-zero): {alt_rate*100:.2f}%")
