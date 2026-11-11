import json, os

check_files = [
    r'D:\Downloads\matreshka_quantum_v11_2026-11-08.json',
    r'D:\Downloads\quantum_v8_session_1775069435083.json',
    r'D:\Downloads\matreshka_session_2026-03-31.json',
    r'D:\Downloads\matreshka_session_2026-04-01 (3).json',
    r'D:\Downloads\matreshka_session_2026-04-01.json',
    r'D:\Downloads\matreshka_session_2026-04-02 (1).json',
    r'D:\Downloads\matreshka_session_2026-11-10 (2).json',
    r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json',
]

for p in check_files:
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    logs = d.get('logs', []) if isinstance(d, dict) else d
    dts = []
    for i, e in enumerate(logs):
        dt = e.get('time_since_last_spin')
        if dt is not None: dts.append(round(dt/1000, 1))
        elif i > 0 and 'timestamp' in e and 'timestamp' in logs[i-1]:
            dts.append(round((e['timestamp'] - logs[i-1]['timestamp'])/1000, 1))
    print(f"=== {os.path.basename(p)} (N={len(logs)}) ===")
    print(f"First 15 dt(s): {dts[:15]}")
    print(f"Last  10 dt(s): {dts[-10:]}")
