import os, json, glob, hashlib

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json')
)

for p in paths:
    if not os.path.exists(p): continue
    with open(p, 'r', encoding='utf-8') as f: d = json.load(f)
    logs = d.get('logs', []) if isinstance(d, dict) else d
    fast_idx = []
    for i, e in enumerate(logs):
        dt = e.get('time_since_last_spin')
        if dt is None and i > 0 and 'timestamp' in e and 'timestamp' in logs[i-1]:
            dt = e['timestamp'] - logs[i-1]['timestamp']
        if dt is not None and i > 0 and dt < 3000:
            res = e.get('input_result') or e.get('actual_outcome') or e.get('outcome')
            fast_idx.append((i, round(dt/1000, 2), res))
    if fast_idx:
        print(f"{os.path.basename(p)} (N={len(logs)}): fast={fast_idx[:10]}{'...' if len(fast_idx)>10 else ''} (total fast={len(fast_idx)})")
