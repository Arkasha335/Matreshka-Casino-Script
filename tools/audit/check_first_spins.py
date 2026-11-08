import json
with open(r'd:/Downloads/matreshka_session_2026-11-08 (1).json', 'r', encoding='utf-8') as f:
    d = json.load(f)

for i in range(7):
    print(d['logs'][i])
