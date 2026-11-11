import os, json, glob, hashlib

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json')
)

seen_hashes = {}
valid_sessions = []

print(f"{'#':>2} | {'Filename':<40} | {'Spins':>5} | {'R/B/Z':<12} | {'Format':<12} | {'Profile':<19} | {'Note'}")
print("-" * 115)

for idx, p in enumerate(paths, 1):
    fname = os.path.basename(p)
    try:
        with open(p, 'r', encoding='utf-8') as f:
            d = json.load(f)
    except Exception as e:
        print(f"{idx:>2} | {fname:<40} | ERROR: {e}")
        continue

    logs = d.get('logs', [])
    if not logs and isinstance(d, list):
        logs = d

    outcomes = []
    for entry in logs:
        res = entry.get('input_result') or entry.get('actual_outcome') or entry.get('outcome')
        if res in ('RED', 'BLACK', 'ZERO'):
            outcomes.append(res)

    if not outcomes:
        print(f"{idx:>2} | {fname:<40} |     0 | {'-':<12} | {'empty':<12} | {'-':<19} | No outcomes")
        continue

    h = hashlib.md5(','.join(outcomes).encode()).hexdigest()[:10]
    note = ""
    if h in seen_hashes:
        note = f"DUP of {seen_hashes[h]}"
    else:
        seen_hashes[h] = fname

    meta = d.get('metadata', {}) if isinstance(d, dict) else {}
    prof = meta.get('strategyProfile', meta.get('profile', 'N/A'))
    sample_keys = set(logs[0].keys()) if logs else set()
    fmt = 'v12' if 'current_mode' in sample_keys else ('v11/old' if 'input_result' in sample_keys else 'other')

    r = outcomes.count('RED')
    b = outcomes.count('BLACK')
    z = outcomes.count('ZERO')
    rbz = f"{r}/{b}/{z}"

    print(f"{idx:>2} | {fname[:40]:<40} | {len(outcomes):>5} | {rbz:<12} | {fmt:<12} | {str(prof)[:19]:<19} | {note}")
    if not note:
        valid_sessions.append((p, fname, outcomes, d))

print("-" * 115)
print(f"Total files scanned: {len(paths)} | Unique non-empty sessions: {len(valid_sessions)} | Total unique spins: {sum(len(x[2]) for x in valid_sessions)}")
