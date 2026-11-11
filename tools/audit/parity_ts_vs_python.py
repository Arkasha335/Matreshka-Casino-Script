import glob, hashlib, json, math, os, subprocess, sys
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
            seen.add(h); res.append((fn, outs))
    return res

def geom_sum_factor(n, x=2.025):
    return (math.pow(x, n) - 1.0) / (x - 1.0)

def make_preset(z_spec, t_spec, d_spec):
    specs = {'ZEBRA': z_spec, 'TRANSITION': t_spec, 'DANGER': d_spec}
    def fn(mode, cap, limit):
        cap = max(10_000, cap); limit = max(10_000, limit)
        scale = max(0.15, min(limit, cap / 1.92) / 1_000_000.0)
        b0, n = specs[mode]
        while n > 5 and 1000 * geom_sum_factor(n) > cap: n -= 1
        max_b0 = max(1000, int(math.floor(cap / geom_sum_factor(n) / 100.0) * 100))
        return max(1000, min(limit, max_b0, int(js_round(b0 * scale / 100.0) * 100))), n
    return fn

p_shield = make_preset((1700,10),(1200,10),(1000,10))
p_apex   = make_preset((3500,9), (2000,10),(1200,10))
p_turbo  = make_preset((6000,8), (4000,8), (1700,9))

def solve_exact_budget_x(prev_b, rem_steps, rem_wallet, table_limit, min_x=2.025, max_x=3.20):
    x_table = math.pow(table_limit / max(1, prev_b), 1.0 / rem_steps)
    hi = min(max_x, x_table)
    def geom_sum(x):
        s = 0.0; b = float(prev_b)
        for _ in range(rem_steps):
            b *= x; s += b
        return s
    if hi < min_x:
        if geom_sum(min_x) <= rem_wallet: return min_x, min(table_limit, rem_wallet)
        lo, hi_fb = 1.01, min_x
        if geom_sum(lo) > rem_wallet: return lo, min(table_limit, rem_wallet)
        for _ in range(25):
            mid = 0.5 * (lo + hi_fb)
            if geom_sum(mid) <= rem_wallet: lo = mid
            else: hi_fb = mid
        return lo, min(table_limit, round(prev_b * (lo ** rem_steps)))
    if geom_sum(hi) <= rem_wallet: return hi, min(table_limit, round(prev_b * (hi ** rem_steps)))
    lo = 1.01
    if geom_sum(min_x) > rem_wallet:
        if geom_sum(lo) > rem_wallet: return lo, min(table_limit, rem_wallet)
        hi_w = min_x
        for _ in range(25):
            mid = 0.5 * (lo + hi_w)
            if geom_sum(mid) <= rem_wallet: lo = mid
            else: hi_w = mid
        return lo, min(table_limit, round(prev_b * (lo ** rem_steps)))
    lo = min_x
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        if geom_sum(mid) <= rem_wallet: lo = mid
        else: hi = mid
    return lo, min(table_limit, round(prev_b * (lo ** rem_steps)))

def exact_solver_bet(cdt, step, base_bet, target_steps, bankroll, table_limit, prev_bet):
    if bankroll < 1000: return max(0, int(bankroll))
    base_bet = max(1000, min(base_bet, bankroll, table_limit))
    if cdt <= 0 or step <= 1: return js_round(base_bet)
    rem = max(1, target_steps - step + 1)
    min_tbb = math.ceil((cdt + base_bet) / 0.98)
    pb = prev_bet if (prev_bet is not None and prev_bet > 0) else base_bet
    if rem == 1:
        cap = min(table_limit, bankroll)
        bet = min(min_tbb, cap) if cdt < cap * 0.30 else cap
        return max(1000, min(cap, js_round(bet)))
    opt_x, _ = solve_exact_budget_x(pb, rem, bankroll, table_limit)
    bet = max(min_tbb, js_round(pb * opt_x))
    if rem == 2:
        max_safe = min(math.floor(table_limit * 0.98) - cdt - 100, math.floor((0.98 * bankroll - cdt - 100) / 1.98))
        if max_safe >= math.ceil((cdt + 100) / 0.98):
            bet = min(bet, max_safe)
    return js_round(max(1000, min(bet, table_limit, bankroll)))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = r"C:\Users\user\.gemini\antigravity\brain\8cb8961f-b2d1-43d1-b097-d60fa78963d3\scratch\ts_parity_build"
os.makedirs(OUT_DIR, exist_ok=True)

# 1. Compile production TypeScript engine files into scratch CommonJS modules
cmd = [
    "npx.cmd" if os.name == "nt" else "npx",
    "tsc",
    os.path.join(REPO_ROOT, "lib", "engine", "types.ts"),
    os.path.join(REPO_ROOT, "lib", "engine", "prng-detector.ts"),
    os.path.join(REPO_ROOT, "lib", "engine", "bankroll-manager.ts"),
    "--outDir", OUT_DIR,
    "--module", "commonjs",
    "--target", "es2020",
    "--esModuleInterop",
    "--skipLibCheck",
]
subprocess.run(cmd, check=True, cwd=REPO_ROOT)

# 2. Export real 27 session outcome arrays + write small Node runner in OUT_DIR
sessions = load_clean()
payload = [{"name": fn, "outcomes": outs} for fn, outs in sessions]
payload_path = os.path.join(OUT_DIR, "sessions.json")
with open(payload_path, "w", encoding="utf-8") as f:
    json.dump(payload, f)

node_runner = os.path.join(OUT_DIR, "run_parity.js")
with open(node_runner, "w", encoding="utf-8") as f:
    f.write(r"""
const fs = require('fs');
const path = require('path');
const { BankrollManager } = require('./bankroll-manager.js');
const { PrngDetector } = require('./prng-detector.js');
const { GAME_RULES } = require('./types.js');

const sessions = JSON.parse(fs.readFileSync(path.join(__dirname, 'sessions.json'), 'utf-8'));
const profiles = ['APEX_IDEAL', 'TURBO_HARVEST', 'SHIELD_CONSERVATIVE'];
const limits = [1000000, 2000000];
const banks = [1000000, 2000000, 3800000, 6500000];

const results = [];
for (const profile of profiles) {
  for (const limit of limits) {
    for (const initBank of banks) {
      if (limit === 2000000 && initBank < 2000000) continue;
      for (const s of sessions) {
        let bank = initBank;
        let step = 1;
        let cdt = 0;
        let prevBet = undefined;
        let mode = 'ZEBRA';
        let prevMode = 'ZEBRA';
        let spinsSinceDangerExit = 999;
        let spinsInCurr = 0;
        let seqStart = 'ZEBRA';
        let seqTargetSteps = undefined;
        const hist = [];
        const trace = [];
        for (const outcome of s.outcomes) {
          if (bank < GAME_RULES.MIN_BET) break;
          const cycleCap = bank + cdt;
          const locked = cdt > 0 && BankrollManager.shouldLockZebra(profile, cycleCap, seqStart);
          const effMode = locked ? 'ZEBRA' : mode;
          const params = BankrollManager.getEngineParams(profile, effMode, bank, limit, cdt, cdt > 0 ? seqTargetSteps : undefined);
          const bet = BankrollManager.calculateBet(cdt, step, effMode, params, bank, prevBet, limit);
          const pred = PrngDetector.getRecommendationAndConfidence(hist).recommendation;
          const wasAtStart = cdt === 0 || step === 1;

          trace.push([bet, effMode, step, params.stepsToLimit, Math.round(params.baseBet)]);

          let isWin = false;
          let netProfit = 0;
          if (outcome === 'ZERO') {
            isWin = false;
            netProfit = -bet;
            cdt += bet;
            step += 1;
          } else if (outcome === pred) {
            isWin = true;
            netProfit = Math.round(bet * GAME_RULES.WIN_NET_RATIO);
            cdt = Math.max(0, Math.round(cdt - netProfit));
            if (cdt < 10) cdt = 0;
            if (cdt === 0) step = 1;
          } else {
            isWin = false;
            netProfit = -bet;
            cdt += bet;
            step += 1;
          }
          bank += netProfit;
          hist.push({ outcome, betAmount: bet, betColor: pred, isWin, netProfit });

          if (BankrollManager.usesFastModeDetector(profile)) {
            const nm = PrngDetector.detectModeFast(hist);
            prevMode = nm !== mode ? mode : prevMode;
            spinsInCurr = nm !== mode ? 1 : spinsInCurr + 1;
            mode = nm;
            spinsSinceDangerExit = 999;
          } else {
            const h = PrngDetector.detectModeWithHysteresis(hist, prevMode, mode, spinsSinceDangerExit, spinsInCurr);
            mode = h.mode; prevMode = h.newPrevMode;
            spinsSinceDangerExit = h.newSpinsSinceDangerExit; spinsInCurr = h.newSpinsInCurrentMode;
          }

          if (cdt === 0) {
            seqStart = mode;
            seqTargetSteps = undefined;
          } else if (wasAtStart) {
            seqStart = effMode;
            seqTargetSteps = BankrollManager.getCalibratedLadderConfig(profile, effMode, cycleCap, limit).targetSteps;
          }
          prevBet = bet;
        }
        results.push({ key: `${profile}|${limit}|${initBank}|${s.name}`, bank, trace });
      }
    }
  }
}
fs.writeFileSync(path.join(__dirname, 'ts_results.json'), JSON.stringify(results));
console.log('TS_RUNS=' + results.length);
""")

subprocess.run(["node", node_runner], check=True)
with open(os.path.join(OUT_DIR, "ts_results.json"), "r", encoding="utf-8") as f:
    ts_results = {r["key"]: r for r in json.load(f)}

# 3. Compare spin-by-spin against independent Python reference
py_cfgs = {"APEX_IDEAL": (p_apex, True), "TURBO_HARVEST": (p_turbo, True), "SHIELD_CONSERVATIVE": (p_shield, False)}
mismatches = 0
total_spins = 0
inv_failures = 0

for profile, (fn, is_fast) in py_cfgs.items():
    for limit in [1_000_000, 2_000_000]:
        for init_bank in [1_000_000, 2_000_000, 3_800_000, 6_500_000]:
            if limit == 2_000_000 and init_bank < 2_000_000:
                continue
            for s_name, outs in sessions:
                bank = init_bank
                step = 1
                cdt = 0
                prev_bet = None
                mode = "ZEBRA"
                prev_mode = "ZEBRA"
                sde = 999
                sim = 0
                seq_start = "ZEBRA"
                seq_n = None
                hist = []
                py_trace = []
                for outcome in outs:
                    if bank < 1000:
                        break
                    cycle_cap = bank + cdt
                    locked = cdt > 0 and is_fast and cycle_cap >= 3_000_000 and seq_start == "ZEBRA"
                    eff_mode = "ZEBRA" if locked else mode
                    b0, mode_n = fn(eff_mode, cycle_cap, limit)
                    eff_n = min(mode_n, seq_n) if (cdt > 0 and seq_n is not None) else mode_n
                    bet = exact_solver_bet(cdt, step, b0, eff_n, bank, limit, prev_bet)
                    if bet < 1000 or bet > limit or bet > bank:
                        inv_failures += 1
                    pred = PrngDetectorMirror.get_recommendation_and_confidence(hist)[0]
                    was_at_start = (cdt == 0 or step == 1)
                    py_trace.append([bet, eff_mode, step, eff_n, b0])

                    if outcome == "ZERO":
                        net = -bet; cdt += bet; step += 1
                    elif outcome == pred:
                        net = js_round(bet * 0.98)
                        cdt = max(0, js_round(cdt - net))
                        if cdt < 10: cdt = 0
                        if cdt == 0: step = 1
                    else:
                        net = -bet; cdt += bet; step += 1
                    bank += net
                    hist.append(outcome)

                    if is_fast:
                        raw_m = PrngDetectorMirror.detect_mode(hist)
                        zero10 = sum(1 for x in hist[-10:] if x == "ZERO")
                        nm = "TRANSITION" if (zero10 >= 3 and raw_m == "ZEBRA") else raw_m
                        prev_mode = mode if nm != mode else prev_mode
                        sim = 1 if nm != mode else sim + 1
                        mode = nm
                        sde = 999
                    else:
                        mode, prev_mode, sde, sim = PrngDetectorMirror.detect_mode_with_hysteresis(hist, prev_mode, mode, sde, sim)

                    if cdt == 0:
                        seq_start = mode; seq_n = None
                    elif was_at_start:
                        seq_start = eff_mode
                        seq_n = fn(eff_mode, cycle_cap, limit)[1]
                    prev_bet = bet

                key = f"{profile}|{limit}|{init_bank}|{s_name}"
                ts_rec = ts_results[key]
                total_spins += len(py_trace)
                if ts_rec["bank"] != bank or ts_rec["trace"] != py_trace:
                    mismatches += 1
                    if mismatches <= 3:
                        print("MISMATCH:", key, "PY_BANK=", bank, "TS_BANK=", ts_rec["bank"])
                        for idx, (pt, tt) in enumerate(zip(py_trace, ts_rec["trace"])):
                            if pt != tt:
                                print(f"  First diff spin {idx}: PY={pt} vs TS={tt}")
                                break

print(f"PARITY CHECK: runs={len(ts_results)}, total_spins={total_spins:,}, mismatches={mismatches}, inv_failures={inv_failures}")
if mismatches > 0 or inv_failures > 0:
    sys.exit(1)
