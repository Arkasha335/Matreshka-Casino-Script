import json
import glob
import math

def load_all_sessions():
    files = glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json')
    files.append(r'd:\Downloads\matreshka_quantum_v11_2026-11-08.json')
    files.append(r'd:\Downloads\matreshka_session_2026-11-08.json')
    sessions = []
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logs = data.get('logs', [])
        outcomes = []
        for entry in logs:
            res = entry.get('input_result') or entry.get('actual_outcome')
            if res:
                outcomes.append(res)
        sessions.append({
            'name': fpath.split('\\')[-1],
            'outcomes': outcomes
        })
    return sessions

sessions = load_all_sessions()
print(f"Loaded {len(sessions)} sessions.")
