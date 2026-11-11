import os, sys, math, json
from collections import defaultdict
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror, js_round, GAME_RULES
from research_1_reverse_engineering import load_clean_corpus

sessions = load_clean_corpus()

# First: dissect 2026-11-10 (2)
print("=== DISSECTING USER'S FRESH SESSION: matreshka_session_2026-11-10 (2).json ===")
with open(r'd:\Downloads\matreshka_session_2026-11-10 (2).json', 'r', encoding='utf-8') as f:
    fresh = json.load(f)

logs = fresh['logs']
print(f"Profile: {fresh['metadata']['strategyProfile']} | Init: {fresh['metadata']['initialBankroll']:,} | End: {fresh['metadata']['currentBankroll']:,} | Profit: +{fresh['metadata']['totalProfit']:,}")
print(f"Spins: {len(logs)} | Duration: {fresh['metadata']['durationMs']/60000:.2f} min | Hourly rate: {fresh['metadata']['totalProfit']/(fresh['metadata']['durationMs']/3600000):,.0f} RUB/hr")

# Analyze sequences & mode transitions in 2026-11-10 (2)
seq_mode_counts = defaultdict(lambda: [0, 0, 0]) # [spins, wins, profit]
seq_switched_events = []
cur_seq_start_mode = logs[0]['current_mode']
cur_seq_spins = []
for l in logs:
    m = l['current_mode']
    seq_mode_counts[m][0] += 1
    if l['is_win']: seq_mode_counts[m][1] += 1
    seq_mode_counts[m][2] += l['net_profit']
    cur_seq_spins.append(l)
    if l['is_win']:
        modes_in_seq = [x['current_mode'] for x in cur_seq_spins]
        if len(set(modes_in_seq)) > 1:
            seq_switched_events.append((cur_seq_spins[0]['current_mode'], modes_in_seq, [x['current_bet'] for x in cur_seq_spins], sum(x['net_profit'] for x in cur_seq_spins)))
        cur_seq_spins = []

print("\nBy Mode inside 2026-11-10 (2):")
for m in ['ZEBRA', 'TRANSITION', 'DANGER']:
    sp, wn, pr = seq_mode_counts[m]
    print(f"  {m:<11}: {wn}/{sp} wins ({wn/max(1,sp)*100:5.2f}%) | Net contribution: {pr:+8,d} RUB")

print(f"\nSequences with MID-PROGRESSION mode switch in 2026-11-10 (2): {len(seq_switched_events)}")
for start_m, ms, bets, net in seq_switched_events:
    print(f"  { ' -> '.join(ms) } | Bets: {bets} | Seq Net: {net:+,d} RUB")


# Helper: flexible bankroll simulator for mode switching hypotheses across all 27 sessions
def simulate_corpus(
    profile='APEX_IDEAL',
    init_bank=3_000_000,
    mode_policy='CURRENT',      # 'CURRENT', 'LOCK_ZEBRA', 'LOCK_ALL', 'SOFT_ZEBRA_4', 'NO_COOLDOWN', 'LOCK_ZEBRA_NO_CD', 'UP_ONLY_NO_CD'
    min_tbb_mode='NEW_MODE',    # 'NEW_MODE' (uses curr mode's baseBet) or 'START_MODE'
    adaptive_bank=False,        # True = real evolving bankroll (or reset per session at fixed init_bank)
    enforce_bank_stop=True
):
    total_net = 0
    sessions_won = 0
    sessions_busted = 0
    total_spins = 0
    max_step_ever = 0
    worst_dd = 0
    dead_step_hits = 0
    limit_hits = 0
    results = []

    for s in sessions:
        bank = init_bank
        peak = bank
        sess_dd = 0
        history = []
        step = 1
        cdt = 0
        curr_mode = 'ZEBRA'
        prev_mode = 'ZEBRA'
        s_danger = 999
        s_curr = 0
        seq_start_mode = 'ZEBRA'
        seq_max_profit_mode = 'ZEBRA'
        prev_bet = None
        sess_busted = False
        sess_max_step = 0

        for outcome in s['outcomes']:
            if bank < 1000:
                sess_busted = True
                break

            if step == 1:
                seq_start_mode = curr_mode
                prev_bet = None

            # Determine betting mode according to policy
            if mode_policy == 'CURRENT':
                bet_mode = curr_mode
            elif mode_policy == 'LOCK_ZEBRA':
                bet_mode = 'ZEBRA' if seq_start_mode == 'ZEBRA' else curr_mode
            elif mode_policy == 'LOCK_ZEBRA_4':
                bet_mode = 'ZEBRA' if (seq_start_mode == 'ZEBRA' and step <= 4) else curr_mode
            elif mode_policy == 'LOCK_ZEBRA_5':
                bet_mode = 'ZEBRA' if (seq_start_mode == 'ZEBRA' and step <= 5) else curr_mode
            elif mode_policy == 'LOCK_ZEBRA_NO_CD':
                bet_mode = 'ZEBRA' if seq_start_mode == 'ZEBRA' else curr_mode
            elif mode_policy == 'LOCK_ALL':
                bet_mode = seq_start_mode
            elif mode_policy == 'NO_COOLDOWN':
                bet_mode = curr_mode
            elif mode_policy == 'LOCK_HIGHEST':
                # keep whichever mode between seq_start_mode and curr_mode is higher EV (Z > T > D) UNLESS step>=7 DANGER?
                rank = {'ZEBRA': 3, 'TRANSITION': 2, 'DANGER': 1}
                bet_mode = seq_start_mode if rank[seq_start_mode] >= rank[curr_mode] else curr_mode
                if seq_start_mode == 'ZEBRA': bet_mode = 'ZEBRA'
            else:
                bet_mode = curr_mode

            params = BankrollManagerMirror.get_engine_params(profile, bet_mode, bank)
            bet = BankrollManagerMirror.calculate_bet(cdt, step, bet_mode, params, bank, prev_bet)

            if bet >= 1_000_000:
                limit_hits += 1

            # Check if even winning this bet results in negative sequence return!
            if js_round(bet * 0.98) < cdt:
                dead_step_hits += 1

            rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(history)
            is_win = (outcome == rec and outcome != 'ZERO')

            sess_max_step = max(sess_max_step, step)
            max_step_ever = max(max_step_ever, step)
            total_spins += 1

            if is_win:
                net = js_round(bet * 0.98)
                bank += net
                cdt = max(0, js_round(cdt - net))
                if cdt < 10:
                    cdt = 0
                if cdt == 0:
                    step = 1
                prev_bet = bet
            else:
                net = -bet
                bank -= bet
                cdt += bet
                step += 1
                prev_bet = bet

            if bank > peak: peak = bank
            dd = peak - bank
            if dd > sess_dd: sess_dd = dd

            history.append(outcome)

            if mode_policy in ('NO_COOLDOWN', 'LOCK_ZEBRA_NO_CD', 'FAST_ZEBRA_EXIT'):
                raw = PrngDetectorMirror.detect_mode(history)
                z10 = history[-10:].count('ZERO')
                if z10 >= 3 and raw == 'ZEBRA': raw = 'TRANSITION'
                if mode_policy == 'FAST_ZEBRA_EXIT':
                    # Keep 3-spin DANGER hold ONLY if still losing streak, exit immediately on win or Zebra raw!
                    if step == 1 and raw == 'ZEBRA':
                        curr_mode = 'ZEBRA'
                    else:
                        curr_mode = raw
                else:
                    curr_mode = raw
            else:
                curr_mode, prev_mode, s_danger, s_curr = PrngDetectorMirror.detect_mode_with_hysteresis(
                    history, prev_mode, curr_mode, s_danger, s_curr
                )

        if sess_busted: sessions_busted += 1
        sess_net = bank - init_bank
        total_net += sess_net
        if sess_net > 0: sessions_won += 1
        worst_dd = max(worst_dd, sess_dd)
        results.append({'name': s['name'], 'spins': len(s['outcomes']), 'net': sess_net, 'dd': sess_dd, 'max_step': sess_max_step})

    return {
        'total_net': total_net,
        'won': sessions_won,
        'total': len(sessions),
        'busted': sessions_busted,
        'worst_dd': worst_dd,
        'max_step': max_step_ever,
        'limit_hits': limit_hits,
        'dead_hits': dead_step_hits,
        'spins': total_spins,
        'per_hour_270sp': (total_net / total_spins) * 270.0,
        'results': results,
    }

print("\n=== BENCHMARKING MODE POLICIES ACROSS ALL 27 CLEAN LIVE SESSIONS (2,374 SPINS) ===")
for prof in ['APEX_IDEAL', 'TURBO_HARVEST']:
    for init_b in [2_000_000, 3_500_000]:
        print(f"\n--- Profile: {prof} | Start Bankroll: {init_b:,} RUB ---")
        print(f"{'Policy':<20} | {'Total Net':>12} | {'Est RUB/hr':>10} | {'Won':>6} | {'Worst DD':>11} | {'MaxSt':>5} | {'Lim':>3} | {'Dead'}")
        print("-" * 92)
        for pol in ['CURRENT', 'LOCK_ZEBRA', 'LOCK_ZEBRA_4', 'LOCK_ZEBRA_5', 'LOCK_ALL', 'NO_COOLDOWN', 'LOCK_ZEBRA_NO_CD', 'FAST_ZEBRA_EXIT']:
            r = simulate_corpus(prof, init_b, pol)
            print(f"{pol:<20} | {r['total_net']:>+12,d} | {r['per_hour_270sp']:>+10,.0f} | {r['won']:>2}/{r['total']:<2} | {r['worst_dd']:>11,d} | {r['max_step']:>5} | {r['limit_hits']:>3} | {r['dead_hits']}")
