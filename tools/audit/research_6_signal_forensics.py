import os, sys, math
from collections import defaultdict
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from research_1_reverse_engineering import load_clean_corpus

sessions = load_clean_corpus()

# Split corpus chronologically into First Half (13 sessions, Mar 31 - Apr 5) and Second Half (14 sessions, Apr 5 - Nov 10)
sorted_sess = sorted(sessions, key=lambda x: x['name'])
half = len(sorted_sess) // 2
splits = [
    ("ALL 27 SESSIONS (2,374 spins)", sorted_sess),
    ("EARLY HALF (13 sessions)", sorted_sess[:half]),
    ("RECENT HALF (14 sessions)", sorted_sess[half:]),
]

print("=== SIGNAL FORENSICS: EXACT WINRATE BY (MODE, STATE) & STREAK LENGTH ===")
for label, s_list in splits:
    by_mode = defaultdict(lambda: [0, 0])
    by_state = defaultdict(lambda: [0, 0])
    by_mode_state = defaultdict(lambda: [0, 0])
    by_streak = defaultdict(lambda: [0, 0]) # current non-zero streak before bet

    for s in s_list:
        history = []
        curr_mode = 'ZEBRA'
        prev_mode = 'ZEBRA'
        s_danger = 999
        s_curr = 0
        for outcome in s['outcomes']:
            rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(history)
            is_win = (outcome == rec and outcome != 'ZERO')
            nz = [x for x in history if x != 'ZERO']
            st = PrngDetectorMirror.calc_current_streak(nz)

            by_mode[curr_mode][0] += 1
            by_state[state][0] += 1
            by_mode_state[(curr_mode, state)][0] += 1
            by_streak[min(st, 6)][0] += 1

            if is_win:
                by_mode[curr_mode][1] += 1
                by_state[state][1] += 1
                by_mode_state[(curr_mode, state)][1] += 1
                by_streak[min(st, 6)][1] += 1

            history.append(outcome)
            curr_mode, prev_mode, s_danger, s_curr = PrngDetectorMirror.detect_mode_with_hysteresis(
                history, prev_mode, curr_mode, s_danger, s_curr
            )

    print(f"\n--- {label} ---")
    tot_n = sum(v[0] for v in by_mode.values())
    tot_w = sum(v[1] for v in by_mode.values())
    print(f"TOTAL: {tot_w}/{tot_n} = {tot_w/tot_n*100:.2f}% | Modes: " + ", ".join(f"{m}={by_mode[m][1]}/{by_mode[m][0]} ({by_mode[m][1]/max(1,by_mode[m][0])*100:.2f}%)" for m in ['ZEBRA', 'TRANSITION', 'DANGER']))
    if "ALL" in label:
        print("\nDetailed Breakdown by State (with Z-score vs 48.00% fair roulette):")
        for st, (n, w) in sorted(by_state.items(), key=lambda x: -x[1][0]):
            wr = w/n*100
            se = math.sqrt(0.48*0.52/n)*100
            z = (wr - 48.0)/se
            print(f"  {st:<24} | n={n:4d} | w={w:4d} | WR={wr:5.2f}% | Z={z:+.2f}")

        print("\nDetailed Breakdown inside DANGER mode:")
        for (m, st), (n, w) in sorted(by_mode_state.items(), key=lambda x: -x[1][0]):
            if m == 'DANGER' and n >= 10:
                wr = w/n*100
                print(f"  DANGER + {st:<22} | n={n:4d} | w={w:4d} | WR={wr:5.2f}%")

        print("\nBreakdown by Current Non-Zero Streak Length:")
        for k in sorted(by_streak.keys()):
            n, w = by_streak[k]
            print(f"  Streak {k}{'+' if k==6 else ' '}: {w:4d}/{n:4d} = {w/n*100:5.2f}%")
    else:
        for st in ['ЧЕРЕДОВАНИЕ (FOLLOW)', 'ЧЕРЕДОВАНИЕ (BREAK)', 'ОТСКОК ОТ ПОТОЛКА', 'АЛЬФА-ТРЕНД', 'ВОЛНА (СЛОМ СЕРИИ)', 'ЭХО-ПАТТЕРН']:
            n, w = by_state[st]
            print(f"  {st:<24}: {w:3d}/{n:3d} ({w/max(1,n)*100:5.2f}%)")
