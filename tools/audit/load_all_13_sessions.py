import json
import glob
import os
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Read all 13 sessions (12 original + new one from downloads)
log_dir = r"D:\Vibe\matreshka-quantum\log storage"
all_files = sorted(glob.glob(os.path.join(log_dir, "*.json")))
new_file = r"d:\Downloads\matreshka_quantum_v11_2026-11-08.json"

all_files.append(new_file)

print(f"Total session files including today's test: {len(all_files)}")

all_spins = []
for fpath in all_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    logs = data.get("logs", [])
    print(f"{fname:<40} | Spins: {len(logs):<4} | Profit: {data.get('metadata', {}).get('totalProfit', 0):>12,.2f} | MaxDD: {data.get('metadata', {}).get('maxDrawdown', 0):>12,.2f}")
    all_spins.extend(logs)

print(f"\nTotal spins across all 13 sessions: {len(all_spins)}")
