import os, json, glob, hashlib

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json')
)

seen = {}
print(f"{'#':>2} | {'Filename':<38} | {'N':>4} | {'R/B/Z':<10} | {'MaxSt':>5} | {'Med dt(s)':>9} | {'<2s':>4} | {'Notes'}")
print("-" * 110)

idx = 0
for p in paths:
    if not os.path.exists(p): continue
    fname = os.path.basename(p)
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    logs = d.get('logs', [])
    if not logs and isinstance(d, list): logs = d
    outcomes = []
    dts = []
    for i, e in enumerate(logs):
        res = e.get('input_result') or e.get('actual_outcome') or e.get('outcome')
        if res in ('RED', 'BLACK', 'ZERO'):
            outcomes.append(res)
            dt = e.get('time_since_last_spin')
            if dt is not None and i > 0:
                dts.append(dt / 1000.0)
            elif i > 0 and 'timestamp' in e and 'timestamp' in logs[i-1]:
                dts.append((e['timestamp'] - logs[i-1]['timestamp']) / 1000.0)
    if not outcomes: continue
    h = hashlib.md5(','.join(outcomes).encode()).hexdigest()[:10]
    if h in seen:
        continue
    seen[h] = fname
    idx += 1

    # max color streak (ignoring zero or stopping on zero)
    ms_strict = 0
    cs = 0
    cc = None
    for x in outcomes:
        if x == cc and x != 'ZERO': cs += 1
        else: cs = 1 if x != 'ZERO' else 0; cc = x
        ms_strict = max(ms_strict, cs)

    ms_nz = 0
    cs = 0; cc = None
    for x in outcomes:
        if x == 'ZERO': continue
        if x == cc: cs += 1
        else: cs = 1; cc = x
        ms_nz = max(ms_nz, cs)

    # max non-winning streak against RED/BLACK (including ZERO)
    med_dt = sorted(dts)[len(dts)//2] if dts else -1
    fast_cnt = sum(1 for x in dts if x < 2.0)
    z_pct = outcomes.count('ZERO') / len(outcomes) * 100
    note = []
    if z_pct > 10: note.append(f"HIGH ZERO {z_pct:.1f}%")
    if med_dt >= 0 and med_dt < 3.0: note.append("FAST CLICK TEST?")
    if ms_nz >= 7: note.append(f"NZ_STR={ms_nz}")
    print(f"{idx:>2} | {fname[:38]:<38} | {len(outcomes):>4} | {outcomes.count('RED')}/{outcomes.count('BLACK')}/{outcomes.count('ZERO'):<4} | {ms_strict:>2}/{ms_nz:<2} | {med_dt:>9.1f} | {fast_cnt:>4} | {', '.join(note)}")
