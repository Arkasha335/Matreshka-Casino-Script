import glob, hashlib, json, math, os, sys
from collections import defaultdict
sys.path.append(os.path.dirname(__file__))
from benchmark_v12_5_1_chosen import p_shield_1251, p_apex_1251, p_turbo_1251, run_bench_1m
from verify_final_v12_5_release import precompute_full

paths = sorted(
    glob.glob(r'D:\Vibe\matreshka-quantum\log storage\*.json') +
    [r'D:\Vibe\matreshka-quantum\matreshka_session_2026-04-14.json'] +
    glob.glob(r'D:\Downloads\matreshka*.json') +
    glob.glob(r'D:\Downloads\quantum*.json')
)
skip = {'matreshka_session_2026-03-31.json', 'matreshka_session_2026-04-01 (3).json',
        'matreshka_session_2026-03-31 (1).json', 'matreshka_session_2026-03-31 (2).json', 'matreshka_session_2026-03-31 (3).json'}

seen = set()
step_b = defaultdict(lambda: [0, 0, 0])
bet_b = defaultdict(lambda: [0, 0, 0])
used_files = []
clean_28 = []

for p in paths:
    if not os.path.exists(p): continue
    fn = os.path.basename(p)
    if fn in skip: continue
    with open(p, 'r', encoding='utf-8') as f: jd = json.load(f)
    lgs = jd.get('logs', []) if isinstance(jd, dict) else jd
    if fn == 'matreshka_quantum_v11_2026-11-08.json': lgs = lgs[:22]
    valid = [e for e in lgs if (e.get('input_result') or e.get('actual_outcome') or e.get('outcome')) in ('RED', 'BLACK', 'ZERO')]
    outs = [e.get('input_result') or e.get('actual_outcome') or e.get('outcome') for e in valid]
    h = hashlib.md5(','.join(outs).encode()).hexdigest()
    if not outs or h in seen: continue
    seen.add(h)
    clean_28.append((fn, outs, jd))

    has_step = 0
    for e in valid:
        st = e.get("current_step")
        bet = e.get("current_bet", 0)
        res = e.get("input_result") or e.get("actual_outcome") or e.get("outcome")
        rec = e.get("recommended_action")
        w = e.get("is_win")
        if w is None:
            if rec in ('RED', 'BLACK'):
                w = (res == rec and res != 'ZERO')
            else:
                continue
        if st is None or bet is None: continue
        has_step += 1
        k = f"Step {st:2d}" if st <= 6 else "Step 7+"
        step_b[k][0] += 1
        if w: step_b[k][1] += 1
        if res == "ZERO": step_b[k][2] += 1

        if bet < 5000: bk = "<5k"
        elif bet < 25000: bk = "5k..25k"
        elif bet < 100000: bk = "25k..100k"
        elif bet < 300000: bk = "100k..300k"
        else: bk = "300k+"
        bet_b[bk][0] += 1
        if w: bet_b[bk][1] += 1
        if res == "ZERO": bet_b[bk][2] += 1
    if has_step > 0:
        used_files.append((fn, has_step))

print(f"Unique sessions with real logged step/bet/pred: {len(used_files)}/28 | Total real spins: {sum(x[1] for x in used_files)}")
print("\nALL REAL LOGGED SPINS BY STEP ACROSS ALL 28 SESSIONS:")
for k in sorted(step_b.keys()):
    t, w, z = step_b[k]
    se = math.sqrt(0.48 * 0.52 / t)
    zv = (w/t - 0.48) / se
    print(f"  {k:<8} | N={t:4d} | Win={w:4d} ({w/t*100:5.2f}%, Z={zv:+.2f}) | Zero={z:3d} ({z/t*100:5.2f}%)")

print("\nALL REAL LOGGED SPINS BY ACTUAL BET SIZE ACROSS ALL 28 SESSIONS:")
for k in ["<5k", "5k..25k", "25k..100k", "100k..300k", "300k+"]:
    t, w, z = bet_b[k]
    if t == 0: continue
    se = math.sqrt(0.48 * 0.52 / t)
    zv = (w/t - 0.48) / se
    print(f"  {k:<12} | N={t:4d} | Win={w:4d} ({w/t*100:5.2f}%, Z={zv:+.2f}) | Zero={z:3d} ({z/t*100:5.2f}%)")

# Replay 28 clean sessions (including 2026-11-11.json!) on v12.5.1
tr_28 = precompute_full([x[1] for x in clean_28])
tr_nov11 = precompute_full([x[1] for x in clean_28 if x[0] == 'matreshka_session_2026-11-11.json'])
print("\n=== v12.5.1 BENCHMARK ACROSS ALL 28 CLEAN LIVE SESSIONS (2,512 SPINS) ===")
for name, fn, ncd, zlt in [
    ("SHIELD v12.5.1", p_shield_1251, False, None),
    ("APEX   v12.5.1", p_apex_1251,   True, 3_000_000),
    ("TURBO  v12.5.1", p_turbo_1251,  True, 3_000_000),
]:
    for bank in [2_000_000, 3_800_000, 6_500_000]:
        r28 = run_bench_1m(tr_28, fn, bank, ncd, zlt, False)
        print(f"  {name:<15} Bank={bank/1e6:3.1f}M | R28 Win={r28['win']:>5.1f}% | Med={r28['med']:>+10,.0f}/h | P90={r28['p90']:>+10,.0f}/h | MaxDD={r28['max_dd']:>9,d}")
    rn11 = run_bench_1m(tr_nov11, fn, 3_668_458, ncd, zlt, False)
    print(f"  {name:<15} Nov11@3.67M | Win={rn11['win']:.0f}% | Net/h={rn11['med']:>+10,.0f} | MaxDD={rn11['max_dd']:>9,d}")
