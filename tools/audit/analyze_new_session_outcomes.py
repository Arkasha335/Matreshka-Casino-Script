import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"d:\Downloads\matreshka_quantum_v11_2026-11-08.json", "r", encoding="utf-8") as f:
    data = json.load(f)

logs = data.get("logs", [])
outcomes = [l["input_result"] for l in logs]
print("Server Outcomes in session 2026-11-08:")
print(" ".join(outcomes[:19]))
print(" ".join(outcomes[19:]))

# Color counts
print("\nColor counts:")
print("RED:", outcomes.count("RED"))
print("BLACK:", outcomes.count("BLACK"))
print("ZERO:", outcomes.count("ZERO"))

# Runs and streaks
runs = 1
for i in range(1, len(outcomes)):
    if outcomes[i] != outcomes[i-1]:
        runs += 1

print(f"Total runs in 36 spins: {runs}")
print(f"Alternation rate: {runs / len(outcomes):.2f}")
