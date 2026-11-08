import json
import glob

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

# Let's import the prediction engine logic from prng-detector
# We simulate the exact MPD + Apex Matrix prediction logic
class MPDPredictor:
    def __init__(self):
        self.history = []

    def get_recommendation(self):
        non_zero = [x for x in self.history if x != 'ZERO']
        if len(self.history) == 0:
            return 'RED'
        
        # Micro pattern detector
        if len(non_zero) >= 4:
            l1, l2, l3, l4 = non_zero[-1], non_zero[-2], non_zero[-3], non_zero[-4]
            # Echo A-B-A-B
            if l1 == l3 and l2 == l4 and l1 != l2:
                return 'BLACK' if l1 == 'RED' else 'RED'
            # 3-streak break wave
            if l1 == l2 and l2 == l3 and l4 != l1:
                return 'BLACK' if l1 == 'RED' else 'RED'
        
        if len(non_zero) < 2:
            return non_zero[-1] if non_zero else 'RED'
        
        l1, l2 = non_zero[-1], non_zero[-2]
        
        # Apex matrix
        red_count = non_zero.count('RED')
        black_count = non_zero.count('BLACK')
        alpha = 'NEUTRAL'
        omega = 'NEUTRAL'
        if len(non_zero) > 0:
            if red_count / len(non_zero) > 0.55:
                alpha, omega = 'RED', 'BLACK'
            elif black_count / len(non_zero) > 0.55:
                alpha, omega = 'BLACK', 'RED'
        
        # Max streaks
        max_red = 0
        max_black = 0
        cur_c = None
        cur_l = 0
        for x in non_zero:
            if x == cur_c:
                cur_l += 1
            else:
                if cur_c == 'RED': max_red = max(max_red, cur_l)
                elif cur_c == 'BLACK': max_black = max(max_black, cur_l)
                cur_c = x
                cur_l = 1
        if cur_c == 'RED': max_red = max(max_red, cur_l)
        elif cur_c == 'BLACK': max_black = max(max_black, cur_l)
        
        cur_streak = 0
        cur_col = non_zero[-1]
        for x in reversed(non_zero):
            if x == cur_col: cur_streak += 1
            else: break
            
        cur_max = max_red if cur_col == 'RED' else max_black
        if cur_streak >= cur_max and cur_max > 0:
            return 'BLACK' if cur_col == 'RED' else 'RED'
        elif l1 == l2:
            if l1 == alpha and cur_max > 2:
                return l1
            elif l1 == omega:
                return 'BLACK' if l1 == 'RED' else 'RED'
            else:
                return 'BLACK' if l1 == 'RED' else 'RED'
        else:
            # Alternation follow/break
            last6 = non_zero[-6:]
            if len(last6) >= 4:
                alts = sum(1 for i in range(1, len(last6)) if last6[i] != last6[i-1])
                rate = alts / (len(last6) - 1)
                if rate >= 0.80:
                    return 'BLACK' if l1 == 'RED' else 'RED'
            return l1

    def add_result(self, res):
        self.history.append(res)

print("MPDPredictor initialized successfully.")

def run_simulation(strategy_fn, initial_bankroll=3_800_000):
    total_net = 0
    total_wins = 0
    total_spins = 0
    sessions_won = 0
    max_step_seen = 0
    limit_hits = 0

    for sess in sessions:
        pred = MPDPredictor()
        bank = initial_bankroll
        cdt = 0
        step = 1
        sess_max_step = 0
        sess_won = True
        
        for outcome in sess['outcomes']:
            rec = pred.get_recommendation()
            bet = strategy_fn(step, cdt, bank, initial_bankroll)
            
            # Check table limit
            if bet > 1_000_000:
                limit_hits += 1
                bet = 1_000_000
            
            sess_max_step = max(sess_max_step, step)
            total_spins += 1
            
            if outcome == rec:
                # Win (2% tax)
                win_amt = bet * 1.98
                net = win_amt - bet
                bank += net
                cdt = 0
                step = 1
                total_wins += 1
            else:
                # Loss
                bank -= bet
                cdt += bet
                step += 1
                
            pred.add_result(outcome)
            
        max_step_seen = max(max_step_seen, sess_max_step)
        profit = bank - initial_bankroll
        total_net += profit
        if profit > 0:
            sessions_won += 1

    return {
        'net_profit': total_net,
        'sessions_won': sessions_won,
        'total_sessions': len(sessions),
        'max_step': max_step_seen,
        'limit_hits': limit_hits,
        'winrate': total_wins / total_spins * 100
    }

# Let's test several strategic variants:
# Variant 1: Pure 10-Step TBB (B0 = 1765)
def strat_pure_10(step, cdt, bank, init_bank):
    b0 = 1765
    if step == 1: return b0
    return round((cdt + b0) / 0.98)

# Variant 2: Pure 9-Step TBB (B0 = 3566)
def strat_pure_9(step, cdt, bank, init_bank):
    b0 = 3566
    if step == 1: return b0
    return round((cdt + b0) / 0.98)

# Variant 3: Terminal Snap 10-step:
# Steps 1-9 pure TBB (B0 = 1765). On step 10, snap to 1,000,000 table limit!
def strat_terminal_snap_10(step, cdt, bank, init_bank):
    b0 = 1765
    if step == 1: return b0
    tbb = round((cdt + b0) / 0.98)
    if step >= 10:
        return 1_000_000
    return tbb

# Variant 4: Boosted Steps 2 & 3 with Terminal Snap:
# Step 1: B0 (1765)
# Step 2: 1.15 * TBB
# Step 3: 1.10 * TBB
# Steps 4-9: Pure TBB
# Step 10: 1,000,000
def strat_boosted_snap_10(step, cdt, bank, init_bank):
    b0 = 1765
    if step == 1: return b0
    tbb = round((cdt + b0) / 0.98)
    if step == 2: return round(tbb * 1.15)
    if step == 3: return round(tbb * 1.10)
    if step >= 10: return 1_000_000
    return tbb

# Variant 5: Dynamic Bankroll Step Allocation:
# If bankroll >= 2M, guarantee 10 steps (B0 = 1765).
# If bankroll < 2M, adapt to available steps so we never bet more than bankroll.
def strat_dynamic_adaptive(step, cdt, bank, init_bank):
    # Calculate how many steps remaining we can afford
    # Base bet target: 1765 if bank >= 2M, scaled down if bank < 2M
    b0 = max(1000, min(1765, round(bank / 2_000_000 * 1765)))
    if step == 1: return b0
    tbb = round((cdt + b0) / 0.98)
    # Check if this is the last step before limit
    next_tbb = round(((cdt + tbb) + b0) / 0.98)
    if next_tbb > 1_000_000 or (cdt + tbb + next_tbb) > bank:
        # This step OR next step hits limit/bank!
        # If NEXT step hits limit, should we snap this step or next?
        pass
    if tbb > 500_000:
        # Any step above 500k cannot have a full recovery step after it (since >1M)
        # So this IS the terminal step!
        return min(1_000_000, bank)
    if step == 2: return round(tbb * 1.15)
    if step == 3: return round(tbb * 1.10)
    return tbb

strats = [
    ("Pure 10-Step TBB (B0=1765)", strat_pure_10),
    ("Pure 9-Step TBB (B0=3566)", strat_pure_9),
    ("Terminal Snap 10-Step (B0=1765)", strat_terminal_snap_10),
    ("Boosted 1-2-3 + Terminal Snap (B0=1765)", strat_boosted_snap_10),
    ("Dynamic Terminal Adaptive", strat_dynamic_adaptive),
]

print("\n--- BENCHMARK RESULTS ACROSS ALL 14 SESSIONS (1,046 SPINS) ---")
for name, fn in strats:
    res = run_simulation(fn)
    print(f"\nStrategy: {name}")
    print(f"  Total Net Profit: {res['net_profit']:,.2f} RUB")
    print(f"  Sessions Won:     {res['sessions_won']} / {res['total_sessions']}")
    print(f"  Max Step Reached: {res['max_step']}")
    print(f"  Table Limit Hits: {res['limit_hits']}")
