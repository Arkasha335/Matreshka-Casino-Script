import os, json, glob

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json')
)

print(f"{'Filename':<38} | {'Spins':>5} | {'InitBank':>10} | {'Profit':>10} | {'Dur(m)':>6} | {'RUB/hr':>10} | {'MaxBet':>9} | {'MinBet':>7}")
print("-" * 115)
for p in paths:
    if not os.path.exists(p): continue
    with open(p, 'r', encoding='utf-8') as f: d = json.load(f)
    meta = d.get('metadata', {}) if isinstance(d, dict) else {}
    logs = d.get('logs', []) if isinstance(d, dict) else d
    if not logs: continue
    bets = [l.get('current_bet', l.get('betAmount', 0)) for l in logs if isinstance(l, dict)]
    bets = [b for b in bets if b > 0]
    init_b = meta.get('initialBankroll', 0)
    prof = meta.get('totalProfit', 0)
    dur_ms = meta.get('durationMs', 0)
    if dur_ms == 0 and 'duration' in meta: dur_ms = meta['duration'] * 1000
    if dur_ms == 0 and len(logs) > 1 and 'timestamp' in logs[0]:
        dur_ms = logs[-1]['timestamp'] - logs[0]['timestamp']
    hr = prof / (dur_ms / 3600000.0) if dur_ms > 0 else 0
    if prof != 0 or (bets and max(bets) > 0):
        print(f"{os.path.basename(p)[:38]:<38} | {len(logs):>5} | {int(round(init_b)):>10,d} | {int(round(prof)):>+10,d} | {dur_ms/60000:>6.1f} | {hr:>+10,.0f} | {int(round(max(bets))) if bets else 0:>9,d} | {int(round(min(bets))) if bets else 0:>7,d}")
