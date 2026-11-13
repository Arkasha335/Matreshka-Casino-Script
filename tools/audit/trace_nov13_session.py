import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from tools.audit.engine_mirror import PrngDetectorMirror

def run_trace():
    with open(r'd:\Downloads\matreshka_session_2026-11-13.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    logs = data['logs']
    history = []

    print('=== TRACE OF V14 PREDICTIONS ON NOV 13 SESSION ===')
    for i, x in enumerate(logs):
        spin_res = x['input_result']
        m = PrngDetectorMirror.get_apex_matrix(history) if history else None
        if m:
            pred, conf, reason = PrngDetectorMirror.get_recommendation_and_confidence(history)
        else:
            pred, conf, reason = 'RED', 50, 'АНАЛИЗ'
        log_rec = x['recommended_action']
        log_state = x['server_state_detected']
        
        match = 'OK' if pred == log_rec else f'DIFF(log={log_rec})'
        
        dom = f"{m.get('alphaDominance', 0.5):.1%}" if m else 'N/A'
        cas = m.get('currentStreakLen', 0) if m else 0
        cac = m.get('currentStreakCol', 'NONE') if m else 'NONE'
        exp_r = f"{m.get('avgStreakRed', 1.0):.1f}" if m else 'N/A'
        exp_b = f"{m.get('avgStreakBlack', 1.0):.1f}" if m else 'N/A'
        
        print(f"#{i+1:02d} | cas:{cas} {cac:<5} | Dom:{dom:<6} (E[R]={exp_r}:E[B]={exp_b}) | Pred:{pred:<5} ({conf}%) [{reason:<26}] | Res:{spin_res:<5} | {match}")
        history.append(spin_res)

if __name__ == '__main__':
    run_trace()
