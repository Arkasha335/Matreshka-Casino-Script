"""
Trace predictions of v16.0 on the fresh session
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror

path = 'bot/logs/session_20261117_165453.jsonl'
lines = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]

neural_count = 0
fallback_count = 0
neural_wins = 0
fallback_wins = 0

hist = []
high_step_traces = []

for idx, l in enumerate(lines):
    rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(hist)
    out = l['outcome']
    is_win = (out == rec and out != 'ZERO')

    is_neural = ('НЕЙРОСЕТЬ' in state)
    if is_neural:
        neural_count += 1
        if is_win: neural_wins += 1
    else:
        fallback_count += 1
        if is_win: fallback_wins += 1

    # Check spins 325 to 335
    if 325 <= l['spin'] <= 333:
        feats = PrngDetectorMirror.extract_features(hist)
        p_red = PrngDetectorMirror.forward_neural(feats) if feats else None
        nz = [x for x in hist if x != 'ZERO']
        s = PrngDetectorMirror.calc_current_streak(nz) if nz else 0
        last_c = nz[-1] if nz else None
        high_step_traces.append({
            'spin': l['spin'],
            'step': l['step'],
            'bet': l['bet_amount'],
            'actual_bet_col': l['bet_color'],
            'mirror_rec': rec,
            'conf': conf,
            'state': state,
            'p_red': p_red,
            'streak': s,
            'last_color': last_c,
            'outcome': out,
            'win': is_win
        })

    hist.append(out)

print(f"Total evaluated spins: {len(lines)}")
print(f"Neural predictions: {neural_count} ({neural_count/len(lines)*100:.1f}%), Won: {neural_wins} ({neural_wins/max(1,neural_count)*100:.2f}%)")
print(f"Fallback predictions: {fallback_count} ({fallback_count/len(lines)*100:.1f}%), Won: {fallback_wins} ({fallback_wins/max(1,fallback_count)*100:.2f}%)")

print("\n--- Detailed Trace for Deep Sequence (Spins 325-333) ---")
for t in high_step_traces:
    print(f"Spin #{t['spin']:<3} | Step {t['step']} | Bet: {t['bet']:>9,} ₽ | State: {t['state']:<24} | pRed: {t['p_red']} | Conf: {t['conf']}% | Streak: {t['streak']} {t['last_color']} -> Rec: {t['mirror_rec']:<5} | Out: {t['outcome']:<5} | Win: {t['win']}")
