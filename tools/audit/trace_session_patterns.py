import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"d:\Downloads\matreshka_quantum_v11_2026-11-08.json", "r", encoding="utf-8") as f:
    data = json.load(f)

logs = data.get("logs", [])

print("Step-by-step diagnostic of failed session:")
for i in range(len(logs)):
    l = logs[i]
    print(f"Spin {i+1:2d} | Out: {l['input_result']:<5} | Rec: {l['recommended_action']:<5} | Win: {str(l['is_win']):<5} | Pattern: {l['server_state_detected']}")
