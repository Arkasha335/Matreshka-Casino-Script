import glob
import json
import os

paths = sorted(glob.glob(r"d:\Downloads\matreshka*.json"))
for p in paths:
    with open(p, "r", encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict) and "metadata" in d:
        m = d["metadata"]
        print(
            f"{os.path.basename(p)}: init={m.get('initialBankroll')} "
            f"curr={m.get('currentBankroll')} corr={m.get('balanceCorrection')} "
            f"profit={m.get('totalProfit')} spins={len(d.get('logs', []))}"
        )
