import glob, os, json, hashlib
from collections import defaultdict

all_files = []
# bot logs
for p in sorted(glob.glob(r'bot\logs\*.jsonl')):
    all_files.append(('bot_log_jsonl', p))

# normalized spins
if os.path.exists(r'tools\audit\normalized_spins.json'):
    all_files.append(('normalized', r'tools\audit\normalized_spins.json'))

# other json logs
for p in sorted(glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json')):
    all_files.append(('quantum_storage', p))
for p in sorted(glob.glob(r'D:\Downloads\matreshka*.json')):
    all_files.append(('downloads_matreshka', p))
for p in sorted(glob.glob(r'D:\Downloads\quantum*.json')):
    all_files.append(('downloads_quantum', p))

sessions = []
seen_hashes = set()

# First load bot logs (actual real bot sessions)
for ftype, p in all_files:
    if ftype == 'bot_log_jsonl':
        try:
            lines = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
            outs = [r.get('outcome') for r in lines if r.get('outcome') in ('RED', 'BLACK', 'ZERO')]
            if len(outs) >= 5:
                h = hashlib.md5(','.join(outs).encode()).hexdigest()
                sessions.append({
                    'source': 'bot_log',
                    'file': os.path.basename(p),
                    'path': p,
                    'spins': len(outs),
                    'outcomes': outs,
                    'raw_lines': lines,
                    'hash': h
                })
                seen_hashes.add(h)
        except Exception as e:
            print(f'Error loading {p}: {e}')

# Next load normalized
for ftype, p in all_files:
    if ftype == 'normalized':
        try:
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            by_sess = defaultdict(list)
            for d in data:
                sid = d.get('session_id', 'unknown')
                o = d.get('outcome')
                if o in ('RED', 'BLACK', 'ZERO'):
                    by_sess[sid].append(o)
            for sid, outs in sorted(by_sess.items()):
                if len(outs) >= 10:
                    h = hashlib.md5(','.join(outs).encode()).hexdigest()
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        sessions.append({
                            'source': 'normalized',
                            'file': sid,
                            'path': p,
                            'spins': len(outs),
                            'outcomes': outs,
                            'raw_lines': None,
                            'hash': h
                        })
        except Exception as e:
            print(f'Error loading {p}: {e}')

# Next load other files
for ftype, p in all_files:
    if ftype in ('quantum_storage', 'downloads_matreshka', 'downloads_quantum'):
        try:
            with open(p, encoding='utf-8') as f:
                d = json.load(f)
            logs = d.get('logs', []) if isinstance(d, dict) else d
            outs = [r.get('outcome') or r.get('input_result') or r.get('actual_outcome') for r in logs]
            outs = [x for x in outs if x in ('RED', 'BLACK', 'ZERO')]
            if len(outs) >= 15:
                h = hashlib.md5(','.join(outs).encode()).hexdigest()
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    sessions.append({
                        'source': ftype,
                        'file': os.path.basename(p),
                        'path': p,
                        'spins': len(outs),
                        'outcomes': outs,
                        'raw_lines': logs if isinstance(logs, list) else None,
                        'hash': h
                    })
        except Exception as e:
            pass

print(f"Total unique sessions loaded: {len(sessions)}")
total_spins = sum(s['spins'] for s in sessions)
print(f"Total spins across all unique sessions: {total_spins}")

bot_sess = [s for s in sessions if s['source'] == 'bot_log']
print(f"\nReal Bot Sessions ({len(bot_sess)} sessions, {sum(s['spins'] for s in bot_sess)} spins):")
for s in bot_sess:
    print(f"  {s['file']:<32} | {s['spins']:>5} spins")

other_sess = [s for s in sessions if s['source'] != 'bot_log']
print(f"\nOther Real Historical Sessions ({len(other_sess)} sessions, {sum(s['spins'] for s in other_sess)} spins):")
for s in other_sess:
    print(f"  {s['file']:<45} | {s['spins']:>5} spins | source: {s['source']}")
