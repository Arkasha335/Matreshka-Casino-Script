import json

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)
logs = d["logs"]

wins = [e for e in logs if e["is_win"]]

# Check what would happen if casino rounds each win payout:
# Option 1: round to 10
# Option 2: round to 50
# Option 3: round to 100
# Option 4: ceil to 10
# Option 5: floor to 10
for name, fn in [
    ("exact round(0.98*b)", lambda b: round(b * 0.98)),
    ("round to 10", lambda b: round(round(b * 0.98) / 10.0) * 10),
    ("ceil to 10", lambda b: int(-(-round(b * 0.98) // 10)) * 10),
    ("floor to 10", lambda b: (round(b * 0.98) // 10) * 10),
    ("round to 100", lambda b: round(round(b * 0.98) / 100.0) * 100),
    ("ceil to 100", lambda b: int(-(-round(b * 0.98) // 100)) * 100),
    ("floor to 100", lambda b: (round(b * 0.98) // 100) * 100),
    ("round bet to 100 before 0.98", lambda b: round(round(b / 100.0) * 100 * 0.98)),
]:
    tot = sum(fn(e["current_bet"]) for e in wins)
    diff = tot - sum(e["net_profit"] for e in wins)
    print(f"{name:30s}: diff = {diff:+6d} ₽ (total = {tot:,})")
