import os, sys
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror, js_round
from research_1_reverse_engineering import load_clean_corpus

sessions = {s['name']: s['outcomes'] for s in load_clean_corpus()}

def trace_session(name, init_bank=3_500_000, profile='APEX_IDEAL'):
    print(f"\n================ TRACE: {name} | Init={init_bank:,} | {profile} ================")
    outcomes = sessions[name]
    bank = init_bank
    history = []
    step = 1
    cdt = 0
    curr_mode = 'ZEBRA'
    prev_mode = 'ZEBRA'
    s_danger = 999
    s_curr = 0
    prev_bet = None

    for i, outcome in enumerate(outcomes, 1):
        if bank < 1000:
            print(f"Spin {i}: BUSTED! bank={bank}")
            break
        params = BankrollManagerMirror.get_engine_params(profile, curr_mode, bank)
        bet = BankrollManagerMirror.calculate_bet(cdt, step, curr_mode, params, bank, prev_bet)
        rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(history)
        is_win = (outcome == rec and outcome != 'ZERO')

        old_cdt = cdt
        old_step = step
        if is_win:
            net = js_round(bet * 0.98)
            bank += net
            cdt = max(0, js_round(cdt - net))
            if cdt < 10: cdt = 0
            if cdt == 0: step = 1
        else:
            net = -bet
            bank -= bet
            cdt += bet
            step += 1
        prev_bet = bet

        if old_step >= 6 or (step == 1 and old_step >= 5):
            print(f"Sp {i:3d} | {curr_mode:<10} | St {old_step:2d} | {state[:16]:<16} | Rec={rec:<5} Out={outcome:<5} | Bet={bet:>9,d} | {'WIN' if is_win else 'LOS'} | Net={net:>+10,d} | NewCDT={cdt:>9,d} | Bank={bank:>9,d}")

        history.append(outcome)
        curr_mode, prev_mode, s_danger, s_curr = PrngDetectorMirror.detect_mode_with_hysteresis(
            history, prev_mode, curr_mode, s_danger, s_curr
        )

trace_session('matreshka_session_2026-03-31 (5).json', 3_500_000, 'APEX_IDEAL')
trace_session('matreshka_session_2026-04-01.json', 3_500_000, 'APEX_IDEAL')
trace_session('matreshka_session_2026-04-05 (2).json', 2_000_000, 'APEX_IDEAL')
trace_session('matreshka_session_2026-04-02 (1).json', 3_500_000, 'APEX_IDEAL')
