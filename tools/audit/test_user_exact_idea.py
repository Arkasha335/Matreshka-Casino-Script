import math
from simulate_terminal_strategies import MPDPredictor, sessions

def run_user_exact_benchmark(profile, b0, target_steps, initial_bankroll=3_806_838):
    total_net = 0
    sessions_won = 0
    max_step_overall = 0
    total_spins = 0
    limit_hits = 0
    max_drawdown = 0

    for idx, sess in enumerate(sessions):
        pred = MPDPredictor()
        bank = initial_bankroll
        cdt = 0
        step = 1
        sess_max_step = 0
        peak = bank
        sess_max_dd = 0
        current_bet = b0
        
        for out in sess['outcomes']:
            rec = pred.get_recommendation()
            
            # Dynamic terminal calculation as proposed by user
            terminal_cap = min(1_000_000, math.floor(bank / 1.90))
            
            if step == 1 or cdt <= 0:
                # Dynamic B0 based on bankroll
                if bank < 2_000_000:
                    current_bet = max(500, round(b0 * (bank / 2_000_000)))
                else:
                    current_bet = b0
            else:
                # Steps remaining to terminal step:
                m = max(1, target_steps - step + 1)
                if m == 1:
                    current_bet = min(terminal_cap, bank)
                else:
                    # Calculate exact X to hit terminal_cap at target_steps
                    # from current bet level
                    # If we lost step - 1, we need bet for step
                    # Total steps remaining from (step - 1) was m:
                    # current_bet * X^(m-1) = terminal_cap
                    # So X = (terminal_cap / prev_bet) ^ (1 / m)
                    prev_bet = current_bet
                    ratio = terminal_cap / max(1, prev_bet)
                    if ratio > 1:
                        x = ratio ** (1.0 / m)
                        # Ensure X covers debt with 2% tax
                        min_x = 2.025
                        x = max(min_x, min(2.40, x))
                        next_bet = round(prev_bet * x)
                    else:
                        next_bet = terminal_cap
                        
                    # Guarantee it covers CDT
                    tbb = math.ceil((cdt + b0) / 0.98)
                    current_bet = max(tbb, next_bet)
                    
            bet = min(1_000_000, min(bank, current_bet))
            if current_bet > 1_000_000:
                limit_hits += 1
                
            sess_max_step = max(sess_max_step, step)
            total_spins += 1
            
            if out == rec:
                bank += bet * 0.98
                cdt = 0
                step = 1
                current_bet = b0
            else:
                bank -= bet
                cdt += bet
                step += 1
                
            pred.add_result(out)
            peak = max(peak, bank)
            sess_max_dd = max(sess_max_dd, peak - bank)
            
        profit = bank - initial_bankroll
        total_net += profit
        max_step_overall = max(max_step_overall, sess_max_step)
        max_drawdown = max(max_drawdown, sess_max_dd)
        if profit > 0: sessions_won += 1
        
    print(f"Profile: {profile:20s} (B0={b0}, N={target_steps})")
    print(f"  Total Net Profit: {total_net:12,.2f} RUB")
    print(f"  Sessions Won:     {sessions_won} / {len(sessions)} ({sessions_won/len(sessions)*100:.1f}%)")
    print(f"  Max Step Seen:    {max_step_overall}")
    print(f"  Limit Hits:       {limit_hits}")
    print(f"  Max Drawdown:     {max_drawdown:12,.0f} RUB\n")

print("=== BENCHMARKING USER'S DYNAMIC MULTIPLIER MODEL ===")
run_user_exact_benchmark("APEX 10-STEP (1000)", 1000, 10)
run_user_exact_benchmark("APEX 10-STEP (1200)", 1200, 10)
run_user_exact_benchmark("APEX 10-STEP (1500)", 1500, 10)
run_user_exact_benchmark("TURBO 9-STEP (1500)", 1500, 9)
run_user_exact_benchmark("TURBO 9-STEP (2000)", 2000, 9)
run_user_exact_benchmark("SHIELD 11-STEP (600)", 600, 11)
