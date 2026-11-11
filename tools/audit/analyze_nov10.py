import json, sys, os
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round
from research_3_staking_math import clean_calc_bet

with open(r'd:\Downloads\matreshka_session_2026-11-10 (2).json', 'r', encoding='utf-8') as f:
    d = json.load(f)

logs = d['logs']
outcomes = [l['input_result'] for l in logs]
init_b = d['metadata']['initialBankroll']

print("=== ACTUAL RECORDED LOG: 2026-11-10 (2) ===")
for m in ['ZEBRA', 'TRANSITION', 'DANGER']:
    sub = [l for l in logs if l['current_mode'] == m]
    w = sum(1 for l in sub if l['is_win'])
    p = sum(l['net_profit'] for l in sub)
    print(f"  {m:<11}: {w:2d}/{len(sub):2d} = {w/max(1,len(sub))*100:5.2f}% | Net: {p:+8,d} RUB")

# Compare counterfactual replays on 2026-11-10 (2) at actual Init Bankroll (1,994,104) & Profile TURBO_HARVEST
def replay_nov10(label, cfg, use_no_cd=False, lock_zebra=False):
    bank = init_b
    peak = bank
    max_dd = 0
    history = []
    step = 1
    cdt = 0
    curr_m = 'ZEBRA'
    prev_m = 'ZEBRA'
    sd = 999
    sc = 0
    seq_start = 'ZEBRA'
    prev_b = None
    for out in outcomes:
        active_m = (PrngDetectorMirror.detect_mode(history) if history else 'ZEBRA') if use_no_cd else curr_m
        if use_no_cd and history[-10:].count('ZERO') >= 3 and active_m == 'ZEBRA': active_m = 'TRANSITION'
        if step == 1:
            seq_start = active_m
            prev_b = None
        bm = 'ZEBRA' if (lock_zebra and seq_start == 'ZEBRA') else active_m
        b0, n, sh, xm = cfg[bm]
        bet = clean_calc_bet(cdt, step, b0, n, bank, prev_b, geom_x_min=xm, shape=sh)
        rec, _, _ = PrngDetectorMirror.get_recommendation_and_confidence(history)
        if out == rec and out != 'ZERO':
            net = js_round(bet * 0.98)
            bank += net
            cdt = max(0, js_round(cdt - net))
            if cdt < 10: cdt = 0
            if cdt == 0: step = 1
        else:
            bank -= bet
            cdt += bet
            step += 1
        prev_b = bet
        if bank > peak: peak = bank
        max_dd = max(max_dd, peak - bank)
        history.append(out)
        curr_m, prev_m, sd, sc = PrngDetectorMirror.detect_mode_with_hysteresis(history, prev_m, curr_m, sd, sc)
    dur_hr = d['metadata']['durationMs'] / 3600000.0
    prof = bank - init_b
    print(f"  {label:<44}: Profit = {prof:>+9,d} RUB ({prof/dur_hr:>+9,.0f}/hr) | MaxDD = {max_dd:>7,d}")

print("\n=== COUNTERFACTUAL REPLAY ON 2026-11-10 (2) (83 spins, 24.3 min, Init 1,994,104) ===")
t_cfg = {'ZEBRA':(2500,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}
replay_nov10("v12.4 Actual (TURBO 2M + Hysteresis)", t_cfg, False, False)
replay_nov10("v12.4 + ZEBRA LOCK only", t_cfg, False, True)
replay_nov10("v12.4 + NO_COOLDOWN (fast Z exit)", t_cfg, True, False)
replay_nov10("v12.4 + ZEBRA LOCK + NO_COOLDOWN", t_cfg, True, True)
replay_nov10("PURE 9-step (Z2500 T1800 D1200) NO_CD", {'ZEBRA':(2500,9,'GEOM',2.025), 'TRANSITION':(1800,9,'GEOM',2.025), 'DANGER':(1200,9,'GEOM',2.025)}, True, False)
