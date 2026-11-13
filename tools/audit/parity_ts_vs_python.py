import glob, hashlib, json, math, os, subprocess, sys
sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror, js_round

TABLE_LIMIT = 1_000_000

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

def calc_net_win(bet):
    return ((int(bet) * 98) + 50) // 100

def geom_sum_factor(n, x=2.025):
    return (math.pow(x, n) - 1.0) / (x - 1.0)

def predict_v13(hist, window=15, min_cmax=3):
    if not hist: return 'RED'
    nz = [h for h in hist if h != 'ZERO']
    win_nz = nz[-window:]
    rc = win_nz.count('RED'); bc = len(win_nz) - rc
    ms_r = ms_b = cur = 0; col = None
    for h in win_nz:
        cur = cur + 1 if h == col else 1; col = h
        if col == 'RED': ms_r = max(ms_r, cur)
        else: ms_b = max(ms_b, cur)
    alpha = 'RED' if win_nz and rc / len(win_nz) > 0.55 else ('BLACK' if win_nz and bc / len(win_nz) > 0.55 else 'NEUTRAL')
    omega = 'BLACK' if alpha == 'RED' else ('RED' if alpha == 'BLACK' else 'NEUTRAL')
    cac = nz[-1] if nz else None
    cas = 0
    for h in reversed(nz):
        if h == cac: cas += 1
        else: break
    if len(nz) >= 4:
        L1, L2, L3, L4 = nz[-1], nz[-2], nz[-3], nz[-4]
        if L1 == L3 and L2 == L4 and L1 != L2: return 'BLACK' if L1 == 'RED' else 'RED'
        if L1 == L2 == L3 and L4 != L1: return 'BLACK' if L1 == 'RED' else 'RED'
    if len(nz) < 2: return nz[-1] if nz else 'RED'
    L1, L2 = nz[-1], nz[-2]
    c_max = ms_r if cac == 'RED' else ms_b
    bounce_threshold = max(min_cmax, c_max)
    if cac and c_max > 0 and cas >= bounce_threshold:
        rec = 'BLACK' if cac == 'RED' else 'RED'
    elif L1 == L2:
        if L1 == alpha and c_max > 2:
            rec = L1
        else:
            rec = 'BLACK' if L1 == 'RED' else 'RED'
    else:
        zm = PrngDetectorMirror.get_zebra_momentum(hist)
        rec = L1 if zm['followL1'] else ('BLACK' if L1 == 'RED' else 'RED')
    if L1 == alpha and L2 == omega:
        osb = 0
        for i in range(len(nz) - 2, -1, -1):
            if nz[i] == omega: osb += 1
            else: break
        if osb >= 2: rec = alpha
    return rec

def predict_v15(hist, window=24):
    return predict_v14(hist, window=window)

def predict_v14(hist, window=15):
    if not hist: return 'RED'
    nz = [h for h in hist if h != 'ZERO']
    if len(nz) < 2: return nz[-1] if nz else 'RED'
    win_nz = nz[-window:]
    rc = win_nz.count('RED'); bc = len(win_nz) - rc
    tot = len(win_nz)
    r_r = rc / tot; b_r = bc / tot
    alpha = 'RED' if r_r > 0.55 else ('BLACK' if b_r > 0.55 else 'NEUTRAL')
    omega = 'BLACK' if alpha == 'RED' else ('RED' if alpha == 'BLACK' else 'NEUTRAL')
    alpha_dom = max(r_r, b_r)
    cac = nz[-1]
    cas = 0
    for h in reversed(nz):
        if h == cac: cas += 1
        else: break
    if len(nz) >= 4:
        L1, L2, L3, L4 = nz[-1], nz[-2], nz[-3], nz[-4]
        if L1 == L3 and L2 == L4 and L1 != L2: return 'BLACK' if L1 == 'RED' else 'RED'
        if L1 == L2 == L3 and L4 != L1: return 'BLACK' if L1 == 'RED' else 'RED'
    L1, L2 = nz[-1], nz[-2]
    if cac and cas >= 3:
        rec = 'BLACK' if cac == 'RED' else 'RED'
    elif L1 == L2:
        if L1 == alpha and alpha_dom >= 0.70:
            rec = 'BLACK' if L1 == 'RED' else 'RED'
        else:
            rec = L1
    else:
        zm = PrngDetectorMirror.get_zebra_momentum(hist)
        rec = L1 if zm['followL1'] else ('BLACK' if L1 == 'RED' else 'RED')
    if L1 == alpha and L2 == omega:
        osb = 0
        for i in range(len(nz) - 2, -1, -1):
            if nz[i] == omega: osb += 1
            else: break
        if osb >= 2: rec = alpha
    return rec

def predict_v15(hist, window=24):
    return predict_v14(hist, window=window)

def cfg_1m(profile, mode, cap):
    cap = max(10_000, cap)
    scale = max(0.15, min(TABLE_LIMIT, cap / 1.92) / 1_000_000.0)
    if profile == "SHIELD_CONSERVATIVE":
        b0, n = {'ZEBRA': (1700, 10), 'TRANSITION': (1200, 10), 'DANGER': (1000, 10)}[mode]
    elif profile == "TURBO_HARVEST":
        if cap >= 3_000_000:
            b0, n = {'ZEBRA': (8500, 7), 'TRANSITION': (5000, 8), 'DANGER': (2000, 9)}[mode]
        else:
            b0, n = {'ZEBRA': (6500, 8), 'TRANSITION': (4500, 8), 'DANGER': (2500, 8)}[mode]
    else:
        b0, n = {'ZEBRA': (5000, 8), 'TRANSITION': (2500, 10), 'DANGER': (1400, 10)}[mode]
    while n > 5 and 1000 * geom_sum_factor(n) > cap:
        n -= 1
    max_b0 = max(1000, int(math.floor(cap / geom_sum_factor(n) / 100.0) * 100))
    return max(1000, min(TABLE_LIMIT, max_b0, int(js_round(b0 * scale / 100.0) * 100))), n

def solve_exact_budget_x(prev_b, rem_steps, rem_wallet, min_x=2.025, max_x=3.20):
    x_table = math.pow(TABLE_LIMIT / max(1, prev_b), 1.0 / rem_steps)
    hi = min(max_x, x_table)
    def geom_sum(x):
        s = 0.0; b = float(prev_b)
        for _ in range(rem_steps):
            b *= x; s += b
        return s
    if hi < min_x:
        if geom_sum(min_x) <= rem_wallet: return min_x
        lo, hi_fb = 1.01, min_x
        if geom_sum(lo) > rem_wallet: return lo
        for _ in range(25):
            mid = 0.5 * (lo + hi_fb)
            if geom_sum(mid) <= rem_wallet: lo = mid
            else: hi_fb = mid
        return lo
    if geom_sum(hi) <= rem_wallet: return hi
    lo = 1.01
    if geom_sum(min_x) > rem_wallet:
        if geom_sum(lo) > rem_wallet: return lo
        hi_w = min_x
        for _ in range(25):
            mid = 0.5 * (lo + hi_w)
            if geom_sum(mid) <= rem_wallet: lo = mid
            else: hi_w = mid
        return lo
    lo = min_x
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        if geom_sum(mid) <= rem_wallet: lo = mid
        else: hi = mid
    return lo

def exact_bet_1m(cdt, step, base_bet, target_steps, bankroll, prev_bet):
    int_w = int(math.floor(bankroll))
    if int_w <= 0: return 0
    if int_w < 1000: return int_w
    base_bet = max(1000, min(int(base_bet), int_w, TABLE_LIMIT))
    if cdt <= 0 or step <= 1: return base_bet
    rem = max(1, target_steps - step + 1)
    min_tbb = math.ceil(((cdt + base_bet) * 100) / 98.0)
    while calc_net_win(min_tbb) < cdt + base_bet:
        min_tbb += 1
    pb = int(prev_bet) if (prev_bet is not None and prev_bet > 0) else base_bet
    if rem == 1:
        cap = min(TABLE_LIMIT, int_w)
        bet = min(min_tbb, cap) if cdt < cap * 0.30 else cap
        return max(1000, min(cap, int(math.floor(bet))))
    opt_x = solve_exact_budget_x(pb, rem, int_w)
    bet = max(min_tbb, js_round(pb * opt_x))
    if rem == 2:
        max_pen_t = calc_net_win(TABLE_LIMIT) - cdt - 100
        max_pen_w = math.floor((0.98 * int_w - cdt - 100) / 1.98)
        max_safe = min(max_pen_t, max_pen_w)
        min_be = math.ceil(((cdt + 100) * 100) / 98.0)
        while calc_net_win(min_be) < cdt + 100:
            min_be += 1
        if max_safe >= min_be:
            bet = min(bet, max_safe)
    return max(1000, min(int(math.floor(bet)), TABLE_LIMIT, int_w))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = r"C:\Users\user\.gemini\antigravity\brain\8cb8961f-b2d1-43d1-b097-d60fa78963d3\scratch\ts_parity_build"
os.makedirs(OUT_DIR, exist_ok=True)

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

sessions = load_clean()
payload = [{"name": fn, "outcomes": outs} for fn, outs in sessions]
with open(os.path.join(OUT_DIR, "sessions.json"), "w", encoding="utf-8") as f:
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
const banks = [1000000, 2000000, 3800000, 6500000];

const results = [];
for (const profile of profiles) {
  for (const initBank of banks) {
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
      let zeroInSeq = 0;
      const hist = [];
      const trace = [];
      for (const outcome of s.outcomes) {
        if (bank < GAME_RULES.MIN_BET) break;
        const cycleCap = bank + cdt;
        const zero10 = hist.slice(-10).filter((x) => x.outcome === 'ZERO').length;
        const isZeroShock = profile !== 'SHIELD_CONSERVATIVE' && BankrollManager.isZeroShockActive(zero10, zeroInSeq);
        const locked = cdt > 0 && BankrollManager.shouldLockZebra(profile, cycleCap, seqStart, isZeroShock);
        const effMode = locked ? 'ZEBRA' : mode;
        const params = BankrollManager.getEngineParams(
          profile,
          effMode,
          bank,
          cdt,
          cdt > 0 ? seqTargetSteps : undefined,
          isZeroShock,
          step
        );
        const bet = BankrollManager.calculateBet(cdt, step, effMode, params, bank, prevBet);
        const pred = PrngDetector.getRecommendationAndConfidence(hist).recommendation;
        const wasAtStart = cdt === 0 || step === 1;

        trace.push([bet, effMode, step, params.stepsToLimit, Math.floor(params.baseBet)]);

        let isWin = false;
        let netProfit = 0;
        let nextZeroInSeq = zeroInSeq;
        if (outcome === 'ZERO') {
          isWin = false;
          netProfit = -bet;
          cdt += bet;
          step += 1;
          nextZeroInSeq += 1;
        } else if (outcome === pred) {
          isWin = true;
          netProfit = BankrollManager.calcNetWin(bet);
          cdt = Math.max(0, cdt - netProfit);
          if (cdt === 0) { step = 1; nextZeroInSeq = 0; }
        } else {
          isWin = false;
          netProfit = -bet;
          cdt += bet;
          step += 1;
        }
        zeroInSeq = nextZeroInSeq;
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
          zeroInSeq = 0;
        } else if (wasAtStart) {
          seqStart = effMode;
          seqTargetSteps = BankrollManager.getCalibratedLadderConfig(profile, effMode, cycleCap).targetSteps;
        } else {
          const nextZero10 = hist.slice(-10).filter((x) => x.outcome === 'ZERO').length;
          const nextZeroShock = profile !== 'SHIELD_CONSERVATIVE' && BankrollManager.isZeroShockActive(nextZero10, zeroInSeq);
          if (nextZeroShock && step >= 2) {
            const nextLocked = BankrollManager.shouldLockZebra(profile, bank + cdt, seqStart, true);
            const nextModeCfg = BankrollManager.getCalibratedLadderConfig(profile, nextLocked ? 'ZEBRA' : mode, bank + cdt);
            seqTargetSteps = Math.min(10, Math.max(seqTargetSteps ?? nextModeCfg.targetSteps, nextModeCfg.targetSteps));
          }
        }
        prevBet = bet;
      }
      results.push({ key: `${profile}|${initBank}|${s.name}`, bank, trace });
    }
  }
}
fs.writeFileSync(path.join(__dirname, 'ts_results.json'), JSON.stringify(results));
console.log('TS_RUNS=' + results.length);
""")

subprocess.run(["node", node_runner], check=True)
with open(os.path.join(OUT_DIR, "ts_results.json"), "r", encoding="utf-8") as f:
    ts_results = {r["key"]: r for r in json.load(f)}

mismatches = 0
total_spins = 0
inv_failures = 0

for profile in ["APEX_IDEAL", "TURBO_HARVEST", "SHIELD_CONSERVATIVE"]:
    is_fast = profile != "SHIELD_CONSERVATIVE"
    for init_bank in [1_000_000, 2_000_000, 3_800_000, 6_500_000]:
        for s_name, outs in sessions:
            bank = init_bank; step = 1; cdt = 0; prev_bet = None
            mode = "ZEBRA"; prev_mode = "ZEBRA"; sde = 999; sim = 0
            seq_start = "ZEBRA"; seq_n = None; zero_in_seq = 0
            hist = []; py_trace = []
            for outcome in outs:
                if bank < 1000: break
                cycle_cap = bank + cdt
                zero10 = sum(1 for x in hist[-10:] if x == "ZERO")
                is_zero_shock = is_fast and (zero10 >= 2 or zero_in_seq >= 2)
                locked = cdt > 0 and is_fast and (not is_zero_shock) and cycle_cap >= 3_000_000 and seq_start == "ZEBRA"
                eff_mode = "ZEBRA" if locked else mode
                b0, mode_n = cfg_1m(profile, eff_mode, cycle_cap)
                if cdt > 0 and seq_n is not None:
                    if is_zero_shock and step >= 2:
                        eff_n = min(10, max(seq_n, mode_n), mode_n)
                    else:
                        eff_n = min(mode_n, seq_n)
                else:
                    eff_n = mode_n
                bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
                if bet < 1000 or bet > TABLE_LIMIT or bet > bank:
                    inv_failures += 1
                pred = predict_v15(hist, window=24)
                was_at_start = (cdt == 0 or step == 1)
                py_trace.append([bet, eff_mode, step, eff_n, b0])

                if outcome == "ZERO":
                    net = -bet; cdt += bet; step += 1; zero_in_seq += 1
                elif outcome == pred:
                    net = calc_net_win(bet)
                    cdt = max(0, cdt - net)
                    if cdt == 0: step = 1; zero_in_seq = 0
                else:
                    net = -bet; cdt += bet; step += 1
                bank += net
                hist.append(outcome)

                if is_fast:
                    raw_m = PrngDetectorMirror.detect_mode(hist)
                    zero10_next = sum(1 for x in hist[-10:] if x == "ZERO")
                    nm = "TRANSITION" if (zero10_next >= 3 and raw_m == "ZEBRA") else raw_m
                    prev_mode = mode if nm != mode else prev_mode
                    sim = 1 if nm != mode else sim + 1
                    mode = nm; sde = 999
                else:
                    mode, prev_mode, sde, sim = PrngDetectorMirror.detect_mode_with_hysteresis(hist, prev_mode, mode, sde, sim)

                if cdt == 0:
                    seq_start = mode; seq_n = None; zero_in_seq = 0
                elif was_at_start:
                    seq_start = eff_mode
                    seq_n = cfg_1m(profile, eff_mode, cycle_cap)[1]
                else:
                    next_zero10 = sum(1 for x in hist[-10:] if x == "ZERO")
                    next_zero_shock = is_fast and (next_zero10 >= 2 or zero_in_seq >= 2)
                    if next_zero_shock and step >= 2:
                        next_locked = is_fast and (not True) and (bank + cdt >= 3_000_000) and seq_start == "ZEBRA"
                        next_mode_n = cfg_1m(profile, "ZEBRA" if next_locked else mode, bank + cdt)[1]
                        seq_n = min(10, max(seq_n if seq_n is not None else next_mode_n, next_mode_n))
                prev_bet = bet

            key = f"{profile}|{init_bank}|{s_name}"
            ts_rec = ts_results[key]
            total_spins += len(py_trace)
            if ts_rec["bank"] != bank or ts_rec["trace"] != py_trace:
                mismatches += 1
                if mismatches <= 3:
                    print("MISMATCH:", key, "PY_BANK=", bank, "TS_BANK=", ts_rec["bank"])

print(f"PARITY CHECK v15.0 FINAL APEX (W=24 + SAT_AWARE_ALPHA + DEEP_FADE + ZERO_SHOCK): runs={len(ts_results)}, total_spins={total_spins:,}, mismatches={mismatches}, inv_failures={inv_failures}")
if mismatches > 0 or inv_failures > 0:
    sys.exit(1)
