import os, json, glob

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json')
)

sessions = []
for p in paths:
    if not os.path.exists(p): continue
    with open(p, 'r', encoding='utf-8') as f: d = json.load(f)
    logs = d.get('logs', []) if isinstance(d, dict) else d
    outcomes = [e.get('input_result') or e.get('actual_outcome') or e.get('outcome') for e in logs]
    outcomes = [x for x in outcomes if x in ('RED', 'BLACK', 'ZERO')]
    ts0 = logs[0].get('timestamp') if logs else None
    sessions.append({'path': p, 'name': os.path.basename(p), 'outcomes': outcomes, 'ts0': ts0, 'len': len(outcomes)})

print("=== CHECKING PREFIX / SUBSEQUENCE OVERLAPS ===")
for i in range(len(sessions)):
    for j in range(len(sessions)):
        if i == j: continue
        a, b = sessions[i], sessions[j]
        if a['len'] <= b['len']:
            # Check prefix match
            if b['outcomes'][:a['len']] == a['outcomes']:
                print(f"PREFIX MATCH: {a['name']} ({a['len']}) is exact prefix of {b['name']} ({b['len']})! ts match: {a['ts0'] == b['ts0']}")
            # Check substring match (at least 15 elements)
            elif a['len'] >= 15:
                sa = ','.join(a['outcomes'])
                sb = ','.join(b['outcomes'])
                if sa in sb:
                    print(f"SUBSTRING MATCH: {a['name']} ({a['len']}) inside {b['name']} ({b['len']})")

print("\n=== CHECKING PARTIAL PREFIX OVERLAP (>=10 spins) ===")
for i in range(len(sessions)):
    for j in range(i+1, len(sessions)):
        a, b = sessions[i], sessions[j]
        k = 0
        while k < a['len'] and k < b['len'] and a['outcomes'][k] == b['outcomes'][k]:
            k += 1
        if k >= 10 and k < min(a['len'], b['len']):
            print(f"PARTIAL OVERLAP ({k} spins): {a['name']} ({a['len']}) vs {b['name']} ({b['len']}) | ts: {a['ts0']} vs {b['ts0']}")
