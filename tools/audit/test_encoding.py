import os
import json
import glob

log_dir = r"D:\Vibe\matreshka-quantum\log storage"
for fpath in glob.glob(os.path.join(log_dir, "*.json")):
    with open(fpath, "rb") as f:
        raw = f.read()
    
    # Check if utf-8
    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
        states = set()
        for log in data.get("logs", []):
            st = log.get("server_state_detected")
            if st:
                states.add(st)
        print(f"{os.path.basename(fpath)}: UTF-8 OK, states: {list(states)[:5]}")
    except Exception as e:
        print(f"{os.path.basename(fpath)}: UTF-8 decode failed: {e}")
