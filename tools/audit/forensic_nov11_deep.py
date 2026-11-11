import json, math, os, glob, hashlib, random, sys
from collections import Counter, defaultdict

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror

NOV11_PATH = r"D:\Downloads\matreshka_session_2026-11-11.json"

with open(NOV11_PATH, "r", encoding="utf-8") as f:
    nov11 = json.load(f)

meta = nov11["metadata"]
logs = nov11["logs"]
print("=" * 100)
print("1. FORENSIC DISSECTION OF matreshka_session_2026-11-11.json")
print("=" * 100)
print(f"Date: {meta['date']} | Spins: {len(logs)} | Duration: {meta['durationMs']/60000:.2f} min ({len(logs)/(meta['durationMs']/3600000):.1f} spins/h)")
print(f"Init: {meta['initialBankroll']:,} | Final: {meta['currentBankroll']:,} | Profit: {meta['totalProfit']:+,} | MaxDD (meta): {meta['maxDrawdown']:,}")

# Check exact math rules on payout & rounding across logs
init_b = meta["initialBankroll"]
bal_floor = init_b
bal_round = init_b
bal_ceil = init_b
bal_exact = float(init_b)
bal_no_tax_low = init_b
wins = 0
zeros = 0
non50_wins = []
zero_steps = []
step_outcomes = defaultdict(lambda: [0, 0, 0])  # step -> [total, wins, zeros]

peak_b = init_b
realized_dd = 0
dd_episodes = []
cur_ep_start = None
max_step_seen = 0

for idx, e in enumerate(logs):
    b = e["current_bet"]
    st = e["current_step"]
    res = e["input_result"]
    w = e["is_win"]
    np = e["net_profit"]
    max_step_seen = max(max_step_seen, st)

    if w:
        wins += 1
        f_w = (b * 98) // 100
        r_w = int(math.floor(b * 0.98 + 0.5))
        c_w = math.ceil(b * 0.98)
        ex_w = b * 0.98
        bal_floor += f_w
        bal_round += r_w
        bal_ceil += c_w
        bal_exact += ex_w
        if b % 50 != 0:
            non50_wins.append((idx, b, np, f_w, r_w, c_w, round(b * 0.02, 2)))
    else:
        bal_floor -= b
        bal_round -= b
        bal_ceil -= b
        bal_exact -= b
        if res == "ZERO":
            zeros += 1
            zero_steps.append((idx, st, b, e["current_mode"]))

    step_outcomes[st][0] += 1
    if w: step_outcomes[st][1] += 1
    if res == "ZERO": step_outcomes[st][2] += 1

    if e["current_balance"] > peak_b:
        peak_b = e["current_balance"]
        if cur_ep_start is not None:
            dd_episodes.append(cur_ep_start)
            cur_ep_start = None
    else:
        d = peak_b - e["current_balance"]
        if st >= 5:
            if cur_ep_start is None:
                cur_ep_start = {"peak": peak_b, "min_bal": e["current_balance"], "max_dd": d, "start_idx": idx, "end_idx": idx, "max_step": st, "end_win": False}
            else:
                cur_ep_start["min_bal"] = min(cur_ep_start["min_bal"], e["current_balance"])
                cur_ep_start["max_dd"] = max(cur_ep_start["max_dd"], d)
                cur_ep_start["end_idx"] = idx
                cur_ep_start["max_step"] = max(cur_ep_start["max_step"], st)

print(f"Total Wins: {wins}/{len(logs)} ({wins/len(logs)*100:.2f}%), NonZero Wins: {wins}/{len(logs)-zeros} ({wins/max(1,len(logs)-zeros)*100:.2f}%), Zeros: {zeros}/{len(logs)} ({zeros/len(logs)*100:.2f}%)")
print(f"Rounding audit vs reported final {meta['currentBankroll']:,}:")
print(f"  floor(0.98*b): {bal_floor:,} (diff vs reported: {bal_floor - meta['currentBankroll']:+d})")
print(f"  round(0.98*b): {bal_round:,} (diff vs floor: {bal_round - bal_floor:+d})")
print(f"  ceil(0.98*b) : {bal_ceil:,} (diff vs floor: {bal_ceil - bal_floor:+d})")
print(f"  exact 0.98*b : {bal_exact:,.2f} (diff vs floor: {bal_exact - bal_floor:+.2f})")
print(f"  Non-multiple-of-50 winning bets count: {len(non50_wins)}")
print("  Note: script ended with ...822 (4,004,822), user saw ...871 in game (+49 diff).")
print(f"  Sum of floor losses vs ceil gains on non50 wins: +ceil diff={bal_ceil - bal_floor}, +round diff={bal_round - bal_floor}")

# Print top non50 wins and also check ALL step >= 6 sequences in nov11!
print(f"\nZero events ({len(zero_steps)}): {zero_steps}")
print("\nPer-Step Breakdown in Nov 11:")
for st in sorted(step_outcomes):
    tot, wn, zr = step_outcomes[st]
    print(f"  Step {st:2d}: Total={tot:3d} | Wins={wn:3d} ({wn/tot*100:5.1f}%) | Zero={zr:2d} ({zr/tot*100:4.1f}%)")

# Print full sequence of the two biggest drawdowns (step >= 5)
print("\nMajor Drawdown Sequences (where step >= 5 reached):")
i = 0
while i < len(logs):
    if logs[i]["current_step"] >= 5:
        # walk back to step 1
        s_idx = i
        while s_idx > 0 and logs[s_idx]["current_step"] > 1:
            s_idx -= 1
        # walk forward until step returns to 1 or end
        e_idx = i + 1
        while e_idx < len(logs) and logs[e_idx]["current_step"] > 1:
            e_idx += 1
        seq_logs = logs[s_idx:e_idx]
        max_st = max(x["current_step"] for x in seq_logs)
        tot_risked = sum(x["current_bet"] for x in seq_logs[:-1]) + seq_logs[-1]["current_bet"]
        print(f"\n  --- Episode Spins #{s_idx+1}..#{e_idx} (MaxStep={max_st}, FinalSpinWin={seq_logs[-1]['is_win']}, NetEpisode={sum(x['net_profit'] for x in seq_logs):+,}) ---")
        for j, x in enumerate(seq_logs):
            idx_g = s_idx + j + 1
            print(f"    #{idx_g:3d} Step {x['current_step']} | Mode={x['current_mode']:<10} | State={x['server_state_detected']:<22} | Rec={x['recommended_action']:<5} Actual={x['input_result']:<5} | Bet={x['current_bet']:>9,d} | Win={str(x['is_win']):<5} | Bal={x['current_balance']:>9,d}")
        i = e_idx
    else:
        i += 1

# Also check manual edits or anomalies in current_bet vs solver
print("\nChecking all spins in Nov 11 where time_since_last_spin or bet looks manual/interesting, or high drawdown moments:")
cum_bal = init_b
for idx, x in enumerate(logs):
    if not x["is_win"] and x["current_bet"] >= 50000:
        pass
    # check if prev bet * 2.025 > bet or strange jump
    if idx > 0 and x["current_step"] > 1:
        pb = logs[idx-1]["current_bet"]
        ratio = x["current_bet"] / pb
        if ratio < 1.9 or ratio > 2.6:
            print(f"  Anomalous bet step ratio at spin #{idx+1}: Step {x['current_step']}, prevBet={pb:,}, curBet={x['current_bet']:,} (ratio={ratio:.2f}), isWin_prev={logs[idx-1]['is_win']}")

# ================================================================================================
# 2. MULTI-SESSION RNG FORENSICS ACROSS ALL UNIQUE LIVE SESSIONS (NOW INCLUDING 2026-11-11.json!)
# ================================================================================================
print("\n" + "=" * 100)
print("2. RIGOROUS STATISTICAL FORENSICS: ALL UNIQUE SESSIONS (FAIR 50-SLOT RNG TEST)")
print("=" * 100)

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json')
)
skip = {'matreshka_session_2026-03-31.json', 'matreshka_session_2026-04-01 (3).json',
        'matreshka_session_2026-03-31 (1).json', 'matreshka_session_2026-03-31 (2).json', 'matreshka_session_2026-03-31 (3).json'}

clean_sessions = []
seen = set()
for p in paths:
    if not os.path.exists(p): continue
    fn = os.path.basename(p)
    if fn in skip: continue
    with open(p, 'r', encoding='utf-8') as f: d = json.load(f)
    lgs = d.get('logs', []) if isinstance(d, dict) else d
    if fn == 'matreshka_quantum_v11_2026-11-08.json': lgs = lgs[:22]
    outs = [e.get('input_result') or e.get('actual_outcome') or e.get('outcome') for e in lgs]
    valid = [e for e in lgs if (e.get('input_result') or e.get('actual_outcome') or e.get('outcome')) in ('RED', 'BLACK', 'ZERO')]
    outs = [e.get('input_result') or e.get('actual_outcome') or e.get('outcome') for e in valid]
    h = hashlib.md5(','.join(outs).encode()).hexdigest()
    if outs and h not in seen:
        seen.add(h)
        clean_sessions.append((fn, outs, valid))

total_spins = sum(len(x[1]) for x in clean_sessions)
all_outs = [o for _, outs, _ in clean_sessions for o in outs]
c_all = Counter(all_outs)
print(f"Clean Sessions: {len(clean_sessions)} | Total Unique Spins: {total_spins}")
p_z = c_all['ZERO'] / total_spins
se_z = math.sqrt(0.04 * 0.96 / total_spins)
z_stat_zero = (p_z - 0.04) / se_z
print(f"Color Counts: RED={c_all['RED']} ({c_all['RED']/total_spins*100:.2f}%), BLACK={c_all['BLACK']} ({c_all['BLACK']/total_spins*100:.2f}%), ZERO={c_all['ZERO']} ({p_z*100:.2f}%)")
print(f"  Zero vs fair 4.00%: diff={(p_z-0.04)*100:+.2f}%, Z-score={z_stat_zero:+.2f}")

# Zero gaps / clustering test
gaps = []
close_gaps_5 = 0
close_gaps_10 = 0
total_zero_pairs = 0
for fn, outs, _ in clean_sessions:
    z_idx = [i for i, o in enumerate(outs) if o == 'ZERO']
    for k in range(1, len(z_idx)):
        g = z_idx[k] - z_idx[k - 1]
        gaps.append(g)
        total_zero_pairs += 1
        if g <= 5: close_gaps_5 += 1
        if g <= 10: close_gaps_10 += 1

mean_gap = sum(gaps) / len(gaps)
var_gap = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
# Under Geom(p), expected mean = 1/p, expected variance = (1-p)/p^2
exp_p = c_all['ZERO'] / total_spins
exp_var = (1 - exp_p) / (exp_p ** 2)
exp_close5 = (1 - (1 - exp_p) ** 5) * 100
exp_close10 = (1 - (1 - exp_p) ** 10) * 100
print(f"Zero Clustering Test ({total_zero_pairs} intervals):")
print(f"  Mean gap = {mean_gap:.2f} (1/p={1/exp_p:.2f}) | Empirical Var = {var_gap:.1f} vs Geom Expected Var = {exp_var:.1f} (Fano/Dispersion Ratio = {var_gap/exp_var:.2f}x)")
print(f"  Intervals <= 5 spins: {close_gaps_5}/{total_zero_pairs} ({close_gaps_5/total_zero_pairs*100:.1f}%) vs Expected {exp_close5:.1f}%")
print(f"  Intervals <= 10 spins: {close_gaps_10}/{total_zero_pairs} ({close_gaps_10/total_zero_pairs*100:.1f}%) vs Expected {exp_close10:.1f}%")

# Step-correlated risk test across ALL logged sessions that record real current_step & current_bet!
step_buckets = defaultdict(lambda: [0, 0, 0])  # bucket -> [total, wins, zeros]
bet_buckets = defaultdict(lambda: [0, 0, 0])
for fn, outs, entries in clean_sessions:
    for e in entries:
        st = e.get("current_step")
        w = e.get("is_win")
        bet = e.get("current_bet", 0)
        res = e.get("input_result") or e.get("actual_outcome") or e.get("outcome")
        rec = e.get("recommended_action")
        if st is None or w is None or rec not in ('RED', 'BLACK'):
            continue
        b_st = f"Step {st}" if st <= 5 else "Step 6+"
        step_buckets[b_st][0] += 1
        if w: step_buckets[b_st][1] += 1
        if res == 'ZERO': step_buckets[b_st][2] += 1

        if bet < 5000: bb = "<5k"
        elif bet < 25000: bb = "5k..25k"
        elif bet < 100000: bb = "25k..100k"
        else: bb = "100k+"
        bet_buckets[bb][0] += 1
        if w: bet_buckets[bb][1] += 1
        if res == 'ZERO': bet_buckets[bb][2] += 1

print("\nANTI-PLAYER / HIGH-STEP BIAS TEST (Using actual logged bets & steps across ALL logged sessions):")
for k in sorted(step_buckets.keys()):
    t, w, z = step_buckets[k]
    se_w = math.sqrt(0.48 * 0.52 / t) if t > 0 else 1
    zw = ((w/t) - 0.48) / se_w if t > 0 else 0
    print(f"  {k:<8} | N={t:4d} | Win={w:4d} ({w/t*100:5.2f}%, Z vs 48%={zw:+.2f}) | Zero={z:3d} ({z/t*100:5.2f}%)")

print("\nBet Size Bias Test:")
for k in ["<5k", "5k..25k", "25k..100k", "100k+"]:
    t, w, z = bet_buckets[k]
    if t == 0: continue
    se_w = math.sqrt(0.48 * 0.52 / t)
    zw = ((w/t) - 0.48) / se_w
    print(f"  {k:<10} | N={t:4d} | Win={w:4d} ({w/t*100:5.2f}%, Z vs 48%={zw:+.2f}) | Zero={z:3d} ({z/t*100:5.2f}%)")

# Test Alpha dominance / skew & streak distribution vs 10,000 exact fair 50-slot Monte Carlo sessions!
print("\nALPHA DOMINANCE & STREAK TAIL TEST (Empirical vs 10,000 Fair 50-Slot Roulette Sim Sessions):")
emp_streaks = Counter()
emp_max_streaks = []
alpha_counts_w = {10: [0,0], 15: [0,0], 20: [0,0], 30: [0,0]} # [windows with >=60% dominance, total windows]
alpha_persistence_w = {10: [0,0], 15: [0,0], 20: [0,0], 30: [0,0]} # if alpha (!= NEUTRAL at >55%), next non-zero matches alpha?

for fn, outs, _ in clean_sessions:
    nz = [o for o in outs if o != 'ZERO']
    cur = 0; prev = None; m_st = 0
    for o in nz:
        cur = cur + 1 if o == prev else 1
        prev = o
        m_st = max(m_st, cur)
    # Count exact streak episodes
    cur = 0; prev = None
    for o in nz:
        if o == prev: cur += 1
        else:
            if cur > 0: emp_streaks[cur] += 1
            cur = 1; prev = o
    if cur > 0: emp_streaks[cur] += 1
    emp_max_streaks.append(m_st)

    for W in [10, 15, 20, 30]:
        for idx in range(W, len(nz)):
            win = nz[idx-W:idx]
            rc = win.count('RED')
            frac = max(rc, W - rc) / W
            alpha_counts_w[W][1] += 1
            if frac >= 0.60: alpha_counts_w[W][0] += 1
            if frac > 0.55:
                dom_col = 'RED' if rc > W - rc else 'BLACK'
                alpha_persistence_w[W][1] += 1
                if nz[idx] == dom_col: alpha_persistence_w[W][0] += 1

# Exact streak lengths across all sessions including ZERO as streak breaker vs pure color runs
print("  Empirical Non-Zero Run Lengths across 28 Sessions vs Fair Geometric P(len >= L) = 0.5^(L-1):")
tot_runs = sum(emp_streaks.values())
for L in range(1, 13):
    cnt_ge = sum(v for k, v in emp_streaks.items() if k >= L)
    exp_pct = (0.5 ** (L - 1)) * 100
    emp_pct = cnt_ge / tot_runs * 100
    exp_cnt = tot_runs * (0.5 ** (L - 1))
    print(f"    Run >= {L:2d}: Empirical={cnt_ge:4d}/{tot_runs} ({emp_pct:6.2f}%) | Fair Expected={exp_cnt:6.1f} ({exp_pct:6.2f}%)")

print("\n  Alpha Emergence & Persistence by Window W (Non-Zero Spins):")
for W in [10, 15, 20, 30]:
    d_hits, d_tot = alpha_counts_w[W]
    p_hits, p_tot = alpha_persistence_w[W]
    # Simulate exact fair Binomial(W, 0.5) probability of max(k, W-k)/W >= 0.60
    mc_dom = 0
    rng = random.Random(42 + W)
    for _ in range(20000):
        rc = sum(1 for _ in range(W) if rng.random() < 0.5)
        if max(rc, W - rc) / W >= 0.60:
            mc_dom += 1
    print(f"    Window W={W:2d}: Skew>=60% in {d_hits:4d}/{d_tot} ({d_hits/d_tot*100:5.2f}%) [Fair Binomial={mc_dom/20000*100:5.2f}%] | Alpha Next-Spin Hit Rate={p_hits}/{p_tot} ({p_hits/p_tot*100:5.2f}% vs 50.0% random)")

# Also check prediction accuracy per server_state_detected AND test APEX Matrix window sensitivity!
print("\n" + "=" * 100)
print("3. PREDICTION ENGINE DIAGNOSTICS (ACCURACY BY STATE & WINDOW 12/15/20/30)")
print("=" * 100)
state_stats = defaultdict(lambda: [0, 0, 0])  # state -> [total, wins, zeros]
for fn, outs, _ in clean_sessions:
    hist = []
    for o in outs:
        pred = PrngDetectorMirror.get_recommendation_and_confidence(hist)
        rec, conf, st_lbl = pred
        hist.append(o)
        state_stats[st_lbl][0] += 1
        if o == rec and o != 'ZERO': state_stats[st_lbl][1] += 1
        if o == 'ZERO': state_stats[st_lbl][2] += 1

for st_lbl, (t, w, z) in sorted(state_stats.items(), key=lambda kv: -kv[1][0]):
    print(f"  {st_lbl:<22} | N={t:4d} ({t/total_spins*100:4.1f}%) | Win={w:4d} ({w/t*100:5.2f}%) | Zero={z:3d} ({z/t*100:4.1f}%) | NonZeroWin={w/max(1,t-z)*100:5.2f}%")

# Test rolling window W for getApexMatrix in Python mirror (strictly read-only benchmark!)
def test_apex_window(W):
    tot = w = 0
    for fn, outs, _ in clean_sessions:
        hist = []
        for o in outs:
            # temporarily compute apex matrix with window W
            nz = [h for h in hist if h != 'ZERO'][-W:]
            rc = nz.count('RED'); bc = nz.count('BLACK')
            ms_r = ms_b = cur = 0; col = None
            for h in nz:
                cur = cur + 1 if h == col else 1
                col = h
                if col == 'RED': ms_r = max(ms_r, cur)
                else: ms_b = max(ms_b, cur)
            alpha = 'RED' if nz and rc/len(nz) > 0.55 else ('BLACK' if nz and bc/len(nz) > 0.55 else 'NEUTRAL')
            omega = 'BLACK' if alpha == 'RED' else ('RED' if alpha == 'BLACK' else 'NEUTRAL')
            cac = nz[-1] if nz else None
            cas = 0
            for i in range(len(nz)-1, -1, -1):
                if nz[i] == cac: cas += 1
                else: break
            # Replicate get_recommendation_and_confidence using parameterized W:
            nz_all = [h for h in hist if h != 'ZERO']
            rec = 'RED'
            if len(nz_all) == 0: rec = 'RED'
            elif len(nz_all) >= 4 and nz_all[-1]==nz_all[-3] and nz_all[-2]==nz_all[-4] and nz_all[-1]!=nz_all[-2]:
                rec = 'BLACK' if nz_all[-1]=='RED' else 'RED'
            elif len(nz_all) >= 4 and nz_all[-1]==nz_all[-2]==nz_all[-3] and nz_all[-4]!=nz_all[-1]:
                rec = 'BLACK' if nz_all[-1]=='RED' else 'RED'
            elif len(nz_all) < 2:
                rec = nz_all[-1]
            else:
                L1, L2 = nz_all[-1], nz_all[-2]
                c_max = ms_r if cac == 'RED' else ms_b
                if cac and cas >= c_max and c_max > 0:
                    rec = 'BLACK' if cac == 'RED' else 'RED'
                elif L1 == L2:
                    if L1 == alpha and c_max > 2: rec = L1
                    elif L1 == omega: rec = 'BLACK' if L1 == 'RED' else 'RED'
                    else: rec = 'BLACK' if L1 == 'RED' else 'RED'
                else:
                    zm = PrngDetectorMirror.get_zebra_momentum(hist)
                    rec = L1 if zm['followL1'] else ('BLACK' if L1 == 'RED' else 'RED')
                if L1 == alpha and L2 == omega:
                    osb = 0
                    for i in range(len(nz_all)-2, -1, -1):
                        if nz_all[i] == omega: osb += 1
                        else: break
                    if osb >= 2: rec = alpha
            tot += 1
            if o == rec and o != 'ZERO': w += 1
            hist.append(o)
    return w, tot, w/tot*100

print("\nApexMatrix Window Sensitivity (Accuracy across all 28 Sessions):")
for W in [10, 12, 15, 20, 25, 30, 50]:
    ww, tt, pct = test_apex_window(W)
    print(f"  Window={W:2d}: {ww}/{tt} ({pct:.2f}%)")
