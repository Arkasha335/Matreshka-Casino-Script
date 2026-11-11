import json, math, glob, os

with open(r"D:\Downloads\matreshka_session_2026-11-11.json", "r", encoding="utf-8") as f:
    d = json.load(f)

logs = d["logs"]
init = d["metadata"]["initialBankroll"]
bal = init

print(f"Total entries: {len(logs)}, Init={init}")
# Test hypotheses for how game might pay 4,004,871 instead of 4,004,822 (+49 diff):
# Hyp 1: ceil(0.98 * bet) = bet - floor(bet * 0.02)
# Hyp 2: game rounds bet or payout to nearest 1, or tax applied differently on something?
# Hyp 3: Print ALL 60 winning entries where bet % 50 != 0, plus ALL entries with small gaps / big gaps (undo/misclick!)
wins_list = []
for i, e in enumerate(logs):
    b = e["current_bet"]
    dt = e["time_since_last_spin"]
    if dt > 40000 or (i > 0 and dt < 2000):
        print(f"  Timing note spin #{i+1}: dt={dt}ms, bet={b}, res={e['input_result']}, step={e['current_step']}, win={e['is_win']}")
    if e["is_win"]:
        ex = b * 0.98
        fl = (b * 98) // 100
        cl = math.ceil(b * 0.98)
        rd = int(math.floor(ex + 0.5))
        wins_list.append((i+1, b, fl, rd, cl, e["net_profit"], dt))

print(f"\nWinning spins total={len(wins_list)}, non-50={sum(1 for x in wins_list if x[1]%50!=0)}")
print("Sum net_profit recorded in log:", sum(e["net_profit"] for e in logs), "=> bal:", init + sum(e["net_profit"] for e in logs))
print("Sum with floor(0.98*b):  ", sum((e["current_bet"]*98)//100 if e["is_win"] else -e["current_bet"] for e in logs), "=>", init + sum((e["current_bet"]*98)//100 if e["is_win"] else -e["current_bet"] for e in logs))
print("Sum with round(0.98*b):  ", sum(int(math.floor(e["current_bet"]*0.98+0.5)) if e["is_win"] else -e["current_bet"] for e in logs), "=>", init + sum(int(math.floor(e["current_bet"]*0.98+0.5)) if e["is_win"] else -e["current_bet"] for e in logs))
print("Sum with ceil(0.98*b):   ", sum(math.ceil(e["current_bet"]*0.98) if e["is_win"] else -e["current_bet"] for e in logs), "=>", init + sum(math.ceil(e["current_bet"]*0.98) if e["is_win"] else -e["current_bet"] for e in logs))
# What if initial bankroll had +11? No, what if payout = round(bet * 1.98) vs round? What if ZERO only costs floor? What if 2% fee is NOT taken when bet... no
# Wait: what if player started with 3,668,458 and in game bet was entered WITHOUT tail digits on big bets, e.g., user typed 706950 instead of 706956?!
print("\nSample winning bets non-multiple of 100:")
for w in wins_list:
    if w[1] % 100 != 0:
        print(f"  spin #{w[0]:3d}: bet={w[1]:>9,d} | log_np={w[5]:>9,d} | floor={w[2]} | round={w[3]} | ceil={w[4]}")

# Also scan ALL 28 logs for any step/bet logs to enlarge our anti-player step-bias sample!
paths = sorted(glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') + [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] + glob.glob(r'D:\Downloads\matreshka*.json') + glob.glob(r'D:\Downloads\quantum*.json'))
print("\nScanning files with current_step/current_bet fields:")
for p in paths:
    with open(p, 'r', encoding='utf-8') as f: jd = json.load(f)
    lgs = jd.get('logs', []) if isinstance(jd, dict) else jd
    if lgs and 'current_step' in lgs[0]:
        print(f"  {os.path.basename(p)}: {len(lgs)} entries, step>=6: {sum(1 for x in lgs if x.get('current_step',0)>=6)}")
