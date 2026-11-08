from simulate_terminal_strategies import MPDPredictor, sessions

def evaluate_production_engine(profile):
    total_net = 0
    sessions_won = 0
    max_step_overall = 0
    total_spins = 0
    limit_hits = 0
    max_drawdown = 0

    for idx, sess in enumerate(sessions):
        pred = MPDPredictor()
        bank = 3_806_838
        cdt = 0
        step = 1
        sess_max_step = 0
        peak = bank
        sess_max_dd = 0
        
        # Mode tracking
        mode = 'ZEBRA'
        
        for out in sess['outcomes']:
            rec = pred.get_recommendation()
            
            # Simple mode detection for simulation
            non_zero = [x for x in pred.history if x != 'ZERO']
            cur_streak = 0
            if non_zero:
                c = non_zero[-1]
                for x in reversed(non_zero):
                    if x == c: cur_streak += 1
                    else: break
            if cur_streak >= 4:
                mode = 'DANGER'
            elif cur_streak >= 2:
                mode = 'TRANSITION'
            else:
                mode = 'ZEBRA'
            
            # Staking calculation
            w_eff = min(bank, 2_000_000)
            if profile == 'TURBO_HARVEST':
                full_b0 = min(3300, max(1200, round(w_eff / 2_000_000 * 3300)))
                s2_boost = 1.05
                s3_boost = 1.00
            elif profile == 'SHIELD_CONSERVATIVE':
                full_b0 = min(800, max(300, round(w_eff / 2_000_000 * 800)))
                s2_boost = 1.00
                s3_boost = 1.00
            else: # APEX_IDEAL
                full_b0 = min(1600, max(600, round(w_eff / 2_000_000 * 1600)))
                s2_boost = 1.12
                s3_boost = 1.06
                
            if mode == 'DANGER':
                b0 = max(500, round(full_b0 * 0.5))
                s2_boost = 1.0
                s3_boost = 1.0
            elif mode == 'TRANSITION':
                b0 = max(500, round(full_b0 * 0.8))
                s2_boost = min(1.05, s2_boost)
                s3_boost = 1.0
            else:
                b0 = full_b0
                
            if cdt <= 0:
                bet = b0
            else:
                tbb = round((cdt + b0) / 0.98)
                if step == 2 and s2_boost > 1.0:
                    bet = round(tbb * s2_boost)
                elif step == 3 and s3_boost > 1.0:
                    bet = round(tbb * s3_boost)
                else:
                    bet = tbb
                    
                # Terminal snap check
                next_cdt = cdt + bet
                next_tbb = (next_cdt + b0) / 0.98
                if next_tbb > 1_000_000 or (next_cdt + next_tbb) > bank:
                    # This is the last playable step before limit or bankroll
                    bet = min(1_000_000, bank)
                    
            bet = min(1_000_000, max(b0, bet))
            sess_max_step = max(sess_max_step, step)
            total_spins += 1
            
            if out == rec:
                bank += bet * 0.98
                cdt = 0
                step = 1
            else:
                bank -= bet
                cdt += bet
                step += 1
                
            pred.add_result(out)
            peak = max(peak, bank)
            sess_max_dd = max(sess_max_dd, peak - bank)
            
        profit = bank - 3_806_838
        total_net += profit
        max_step_overall = max(max_step_overall, sess_max_step)
        max_drawdown = max(max_drawdown, sess_max_dd)
        if profit > 0: sessions_won += 1
        
    print(f"\nProfile: {profile}")
    print(f"  Total Net Profit: {total_net:12,.2f} RUB")
    print(f"  Sessions Won:     {sessions_won} / {len(sessions)} ({sessions_won/len(sessions)*100:.1f}%)")
    print(f"  Max Step Seen:    {max_step_overall}")
    print(f"  Max Drawdown:     {max_drawdown:12,.0f} RUB")

print("=== FINAL INTEGRATED PRODUCTION SIMULATION ON ALL 14 SESSIONS ===")
evaluate_production_engine('APEX_IDEAL')
evaluate_production_engine('TURBO_HARVEST')
evaluate_production_engine('SHIELD_CONSERVATIVE')
