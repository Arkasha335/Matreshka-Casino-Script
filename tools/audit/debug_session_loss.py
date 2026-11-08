from simulate_terminal_strategies import MPDPredictor, sessions, strat_pure_10, strat_terminal_snap_10

def check_sessions(strategy_fn, initial_bankroll=3_806_838):
    for idx, sess in enumerate(sessions):
        pred = MPDPredictor()
        bank = initial_bankroll
        cdt = 0
        step = 1
        max_s = 0
        for out in sess['outcomes']:
            rec = pred.get_recommendation()
            bet = strategy_fn(step, cdt, bank, initial_bankroll)
            if bet > 1_000_000: bet = 1_000_000
            max_s = max(max_s, step)
            if out == rec:
                bank += bet * 0.98
                cdt = 0
                step = 1
            else:
                bank -= bet
                cdt += bet
                step += 1
            pred.add_result(out)
        prof = bank - initial_bankroll
        print(f"Session {idx+1:2d} ({sess['name'][:30]:30s}): Profit = {prof:10.2f} RUB | Max Step = {max_s}")

print("--- Check strat_pure_10 (14/14 won) ---")
check_sessions(strat_pure_10)

print("\n--- Check strat_terminal_snap_10 (14/14 won) ---")
check_sessions(strat_terminal_snap_10)
