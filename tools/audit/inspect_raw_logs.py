import os
import json
import glob
import sys

log_dir = r"D:\Vibe\matreshka-quantum\log storage"
files = glob.glob(os.path.join(log_dir, "*.json"))

print(f"Found {len(files)} JSON files in '{log_dir}':\n")

total_spins = 0
for fpath in sorted(files):
    fname = os.path.basename(fpath)
    fsize = os.path.getsize(fpath)
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            meta = data.get("metadata", {})
            logs = data.get("logs", [])
            print(f"File: {fname} (Size: {fsize} bytes)")
            print(f"  Keys: {list(data.keys())}")
            print(f"  Metadata: {meta}")
            print(f"  Log entries: {len(logs)}")
            if logs:
                print(f"  Sample entry keys: {list(logs[0].keys())}")
                print(f"  First entry: {logs[0]}")
                print(f"  Last entry: {logs[-1]}")
            total_spins += len(logs)
        elif isinstance(data, list):
            print(f"File: {fname} (Size: {fsize} bytes) - Array of {len(data)} items")
            if data:
                print(f"  Sample entry: {data[0]}")
            total_spins += len(data)
        else:
            print(f"File: {fname} - Unknown JSON type: {type(data)}")
    except Exception as e:
        print(f"File: {fname} - ERROR parsing JSON: {e}")
        # Try raw lines
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                print(f"  Raw length: {len(content)}, start: {content[:100]}... end: {content[-100:]}")
        except Exception as e2:
            print(f"  Could not read file: {e2}")
    print("-" * 60)

print(f"\nTotal raw log entries across all files: {total_spins}")
