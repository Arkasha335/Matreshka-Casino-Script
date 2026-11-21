import glob, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from audit_versions_head_to_head import load_all_unique_sessions, predict_v15_0, predict_v15_2
from engine_mirror import PrngDetectorMirror

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions across repository.")

results = {}

for name in ['v15.0 / v15.1', 'v15.2 Synthesized', 'v16.1 APEX-Neural']:
    total_spins = 0
    total_wins = 0
    bot_spins = 0
    bot_wins = 0
    user_spins = 0
    user_wins = 0
    
    for s in sessions:
        outs = s['outcomes']
        str_hist = []
        dict_hist = []
        is_bot = (s['source'] == 'bot_log')
        is_user = ('session_20261119_223110' in s['file'])
        
        for o in outs:
            if name == 'v15.0 / v15.1':
                rec = predict_v15_0(str_hist)
            elif name == 'v15.2 Synthesized':
                rec = predict_v15_2(str_hist)
            elif name == 'v16.1 APEX-Neural':
                res = PrngDetectorMirror.get_recommendation_and_confidence(dict_hist)
                rec = res[0]
                
            win = (rec == o)
            total_spins += 1
            if win: total_wins += 1
            if is_bot:
                bot_spins += 1
                if win: bot_wins += 1
            if is_user:
                user_spins += 1
                if win: user_wins += 1
                
            str_hist.append(o)
            dict_hist.append({'outcome': o, 'betAmount': 1000, 'betColor': rec, 'isWin': win, 'netProfit': 0})
            
    results[name] = {
        'total_spins': total_spins,
        'total_wins': total_wins,
        'total_wr': total_wins / total_spins * 100,
        'bot_spins': bot_spins,
        'bot_wins': bot_wins,
        'bot_wr': bot_wins / bot_spins * 100,
        'user_spins': user_spins,
        'user_wins': user_wins,
        'user_wr': user_wins / user_spins * 100,
    }

print("\n" + "="*85)
print(f"{'Version':25s} | {'All 50 Sess WR':15s} | {'Bot Logs (15) WR':16s} | {'User Test (340) WR':16s}")
print("="*85)
for name, r in results.items():
    print(f"{name:25s} | {r['total_wins']:4d}/{r['total_spins']:4d} ({r['total_wr']:5.2f}%) | {r['bot_wins']:4d}/{r['bot_spins']:4d} ({r['bot_wr']:5.2f}%) | {r['user_wins']:3d}/{r['user_spins']:3d} ({r['user_wr']:5.2f}%)")
print("="*85)
