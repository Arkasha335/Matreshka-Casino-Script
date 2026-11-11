import os, sys, math, random, json, glob, hashlib
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round

def load_clean():
    paths = sorted(
        glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
        [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
        glob.glob(r'D:\Downloads\matreshka*.json') +
        glob.glob(r'D:\Downloads\quantum*.json')
    )
    skip = {'matreshka_session_2026-03-31.json', 'matreshka_session_2026-04-01 (3).json',
            'matreshka_session_2026-03-31 (1).json', 'matreshka_session_2026-03-31 (2).json', 'matreshka_session_2026-03-31 (3).json'}
    res, seen = [], set()
    for p in paths:
        if not os.path.exists(p): continue
        fn = os.path.basename(p)
        if fn in skip: continue
        with open(p, 'r', encoding='utf-8') as f: d = json.load(f)
        logs = d.get('logs', []) if isinstance(d, dict) else d
        if fn == 'matreshka_quantum_v11_2026-11-08.json': logs = logs[:22]
        outs = [e.get('input_result') or e.get('actual_outcome') or e.get('outcome') for e in logs]
        outs = [x for x in outs if x in ('RED', 'BLACK', 'ZERO')]
        h = hashlib.md5(','.join(outs).encode()).hexdigest()
        if outs and h not in seen:
            seen.add(h); res.append(outs)
    return res

def gen_empirical(n_sess=2000, spins_per_sess=150, seed=2026):
    rng = random.Random(seed)
    return [['ZERO' if (u := rng.random()) < 0.0485 else ('RED' if u < 0.5242 else 'BLACK') for _ in range(spins_per_sess)] for _ in range(n_sess)]

def gen_aggressive(n_sess=2000, spins_per_sess=150, seed=7777):
    rng = random.Random(seed)
    out = []
    for _ in range(n_sess):
        arr = []; regime = 'NORMAL'; ttl = rng.randint(12, 25); last_nz = 'RED' if rng.random() < 0.5 else 'BLACK'
        for _ in range(spins_per_sess):
            ttl -= 1
            if ttl <= 0:
                u = rng.random()
                if u < 0.30: regime, ttl = 'CALM', rng.randint(15, 30)
                elif u < 0.75: regime, ttl = 'NORMAL', rng.randint(15, 30)
                else: regime, ttl = 'STREAK_WAVE', rng.randint(10, 18)
            zp = 0.035 if regime == 'CALM' else (0.045 if regime == 'NORMAL' else 0.065)
            if rng.random() < zp: arr.append('ZERO')
            else:
                sp = 0.44 if regime == 'CALM' else (0.50 if regime == 'NORMAL' else 0.62)
                c = last_nz if rng.random() < sp else ('BLACK' if last_nz == 'RED' else 'RED')
                arr.append(c); last_nz = c
        out.append(arr)
    return out

def precompute_full(outcome_lists):
    traces = []
    for outcomes in outcome_lists:
        history = []; curr_h = 'ZEBRA'; prev_h = 'ZEBRA'; sd = 999; sc = 0; seq = []
        for out in outcomes:
            rec, _, _ = PrngDetectorMirror.get_recommendation_and_confidence(history)
            is_win = (out == rec and out != 'ZERO')
            raw = PrngDetectorMirror.detect_mode(history) if history else 'ZEBRA'
            if history[-10:].count('ZERO') >= 3 and raw == 'ZEBRA': raw = 'TRANSITION'
            seq.append((is_win, curr_h, raw))
            history.append(out)
            curr_h, prev_h, sd, sc = PrngDetectorMirror.detect_mode_with_hysteresis(history, prev_h, curr_h, sd, sc)
        traces.append(seq)
    return traces

def build_geom_ladder(b0, N, cap=1_000_000, x_min=2.025):
    bets = [b0]; cdt = b0; prev = b0
    for s in range(2, N + 1):
        rem = N - s + 1
        if rem == 1: bet = cap
        else:
            x = max(x_min, min(2.40, (cap / prev) ** (1.0 / rem)))
            geom = round(prev * x); tbb = math.ceil((cdt + b0) / 0.98)
            bet = max(tbb, geom)
            if rem == 2:
                mp = 979000 - cdt
                if mp >= math.ceil(cdt / 0.98): bet = min(bet, mp)
            bet = min(bet, cap)
        bets.append(bet); cdt += bet; prev = bet
    return bets

def analyze_theoretical_ladder(name, bets, p=0.48, alpha=0.98):
    N = len(bets); q = 1.0 - p; cdt = 0; cond_ev = 0.0; step_pis = []
    for k, b in enumerate(bets, 1):
        reach = q ** (k - 1); pi = alpha * b - cdt
        step_pis.append(pi); cond_ev += reach * p * pi; cdt += b
    avg_len = (1.0 - q**N) / p
    bust_p = q ** N
    print(f"{name:<32} | N={N:2d} | B1={bets[0]:>6,d} | MinPi={min(step_pis):>+7,.0f} | MaxPi={max(step_pis):>+8,.0f} | BustCost={cdt:>9,d} | BustP={bust_p*100:5.3f}% | CondEV/sp={cond_ev/avg_len:>+7.1f}")

print("=== EXTREME B0 CHECK (e.g. B0=1000 vs 3000 vs 5000 vs 10000) UNDER 1M LIMIT & 2% TAX ===")
for b0 in [1000, 1400, 1750, 2500, 3000, 3550, 5000, 10000]:
    max_n = 1; best_bets = [b0]
    for N in range(2, 13):
        bets = build_geom_ladder(b0, N, cap=1_000_000, x_min=2.025)
        cdt = 0; ok = True
        for b in bets:
            if round(b * 0.98) - cdt <= 0 or b > 1_000_000: ok = False; break
            cdt += b
        if ok: max_n = N; best_bets = bets
    analyze_theoretical_ladder(f"MaxN for B0={b0:5d}", best_bets)

def clean_calc_bet(cdt, step, base_bet, target_steps, bankroll, prev_bet, geom_x_min=2.025, shape='GEOM'):
    base_bet = max(1000, base_bet)
    if cdt <= 0 or step <= 1: return min(base_bet, max(1000, bankroll))
    cycle_cap = bankroll + cdt
    terminal_cap = max(1000, min(1_000_000, math.floor(cycle_cap / 1.90)))
    remaining = max(1, target_steps - step + 1)
    min_tbb = math.ceil((cdt + base_bet) / 0.98)
    if remaining == 1:
        return max(1000, js_round(min(min_tbb, terminal_cap, bankroll)))
    if shape == 'FLAT_TBB':
        bet = min_tbb
    else:
        pb = prev_bet if (prev_bet is not None and prev_bet > 0) else base_bet
        dyn_x = max(geom_x_min, min(2.40, math.pow(terminal_cap / max(1, pb), 1.0 / remaining)))
        bet = max(min_tbb, js_round(pb * dyn_x))
    if remaining == 2 and terminal_cap >= 900_000:
        max_pen = math.floor(terminal_cap * 0.98) - cdt - 100
        if max_pen >= math.ceil((cdt + 100) / 0.98):
            bet = min(bet, max_pen)
    return js_round(max(1000, min(bet, 1_000_000, bankroll)))

real_raw = load_clean()
tr_real = precompute_full(real_raw)
tr_A = precompute_full(gen_empirical(2000, 150, 2026))
tr_B = precompute_full(gen_aggressive(2000, 150, 7777))

def sim_tiered(traces, profile, init_bank, no_cd=False, zebra_lock=False):
    def get_cfg(mode, cycle_b):
        if profile == 'SHIELD_CONSERVATIVE':
            if cycle_b >= 1_870_000:
                return {'ZEBRA':(1700,10,'GEOM',2.025), 'TRANSITION':(1200,10,'FLAT_TBB',2.025), 'DANGER':(1000,10,'GEOM',2.025)}[mode]
            else:
                return (1000, 10, 'GEOM', 2.025)
        elif profile == 'APEX_IDEAL':
            if cycle_b >= 3_000_000:
                return {'ZEBRA':(3000,9,'GEOM',2.025), 'TRANSITION':(1500,10,'FLAT_TBB',2.025), 'DANGER':(1000,10,'GEOM',2.025)}[mode]
            elif cycle_b >= 1_870_000:
                return {'ZEBRA':(2000,9,'GEOM',2.025), 'TRANSITION':(1200,10,'FLAT_TBB',2.025), 'DANGER':(1000,10,'GEOM',2.025)}[mode]
            else:
                return (1000, 10, 'GEOM', 2.025)
        else:
            if cycle_b >= 3_000_000:
                return {'ZEBRA':(3500,9,'GEOM',2.025), 'TRANSITION':(2000,9,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}[mode]
            elif cycle_b >= 1_870_000:
                return {'ZEBRA':(2500,9,'GEOM',2.025), 'TRANSITION':(1500,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}[mode]
            else:
                return {'ZEBRA':(1500,9,'GEOM',2.025), 'TRANSITION':(1000,10,'GEOM',2.025), 'DANGER':(1000,10,'GEOM',2.025)}[mode]

    n_sess = len(traces); wins = busts = total_net = total_spins = 0; dds, hrs = [], []
    for seq in traces:
        bank = init_bank; peak = bank; sess_dd = 0; step = 1; cdt = 0; prev_bet = None; seq_start = 'ZEBRA'; busted = False
        for is_win, hyst_mode, raw_mode in seq:
            if bank < 1000: busted = True; break
            active_m = raw_mode if no_cd else hyst_mode
            if step == 1: seq_start = active_m; prev_bet = None
            bm = 'ZEBRA' if (zebra_lock and seq_start == 'ZEBRA') else active_m
            b0, ts, sh, xm = get_cfg(bm, bank + cdt)
            bet = clean_calc_bet(cdt, step, b0, ts, bank, prev_bet, geom_x_min=xm, shape=sh)
            total_spins += 1
            if is_win:
                net = js_round(bet * 0.98); bank += net; cdt = max(0, js_round(cdt - net))
                if cdt < 10: cdt = 0
                if cdt == 0: step = 1
            else:
                bank -= bet; cdt += bet; step += 1
            prev_bet = bet
            if bank > peak: peak = bank
            sess_dd = max(sess_dd, peak - bank)
        sess_net = bank - init_bank; total_net += sess_net
        if sess_net > 0: wins += 1
        if busted: busts += 1
        dds.append(sess_dd); hrs.append(sess_net / len(seq) * 270.0)
    dds.sort(); hrs.sort()
    return {'mean_hr': total_net/total_spins*270, 'med_hr': hrs[len(hrs)//2], 'win': wins/n_sess*100, 'bust': busts/n_sess*100, 'max_dd': dds[-1]}

print("\n=== PROPOSED v12.5 PROFILE SUITE BENCHMARK ===")
for bank_t in [2_000_000, 3_500_000]:
    print(f"\n--- Init Bankroll = {bank_t:,} RUB ---")
    print(f"{'Profile Option':<45} | {'Real Win':>8} {'Real Med/h':>10} {'Real MaxDD':>10} | {'A Win%':>6} {'A Bust%':>7} {'A Med/hr':>10} | {'B Bust%'}")
    print("-" * 116)
    opts = [
        ("SHIELD v12.5 (HYST, FLAT Transition)",    'SHIELD_CONSERVATIVE', False, False),
        ("APEX v12.5-A (NO_CD, Z3000/T1500F/D1000)",'APEX_IDEAL',          True,  False),
        ("APEX v12.5-B (HYST,  Z3000/T1500F/D1000)",'APEX_IDEAL',          False, False),
        ("APEX v12.5-C (NO_CD + ZEBRA_LOCK)",       'APEX_IDEAL',          True,  True),
        ("TURBO v12.5-A (NO_CD)",                   'TURBO_HARVEST',       True,  False),
        ("TURBO v12.5-B (NO_CD + ZEBRA_LOCK)",      'TURBO_HARVEST',       True,  True),
    ]
    for lbl, prof, ncd, zl in opts:
        rr = sim_tiered(tr_real, prof, bank_t, ncd, zl)
        ra = sim_tiered(tr_A, prof, bank_t, ncd, zl)
        rb = sim_tiered(tr_B, prof, bank_t, ncd, zl)
        print(f"{lbl:<45} | {rr['win']:>6.1f}%  {rr['med_hr']:>+10,.0f} {rr['max_dd']:>10,d} | {ra['win']:>5.1f}% {ra['bust']:>6.2f}% {ra['med_hr']:>+10,.0f} | {rb['bust']:>6.2f}%")
