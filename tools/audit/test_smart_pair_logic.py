import sys
sys.path.insert(0, 'tools/audit')
from test_cas2_deep_study import load_clean, get_matrix
from parity_ts_vs_python import exact_bet_1m, calc_net_win
from test_v14_antitunnel_bench import make_cfg
from engine_mirror import PrngDetectorMirror

cfg_apex = make_cfg((5000, 8), (2500, 10), (1400, 10))
cfg_turbo = make_cfg(
    (8500, 7),
    (5000, 8),
    (2000, 9),
    3_000_000,
    (6500, 8),
    (4500, 8),
    (2500, 8),
)

def build_smart_pair_predictor(rule_id=1, window=15):
    def predict(history):
        if not history:
            return 'RED'
        non_zero = [h for h in history if h != 'ZERO']
        if len(non_zero) < 2:
            return non_zero[-1] if non_zero else 'RED'

        matrix = get_matrix(history, window=window)
        cas = matrix['currentActiveStreak']
        cac = matrix['currentActiveColor']
        alpha = matrix['alpha']
        omega = matrix['omega']
        top_r = matrix['alphaDominance']

        # MPD patterns
        if len(non_zero) >= 4:
            L1, L2, L3, L4 = non_zero[-1], non_zero[-2], non_zero[-3], non_zero[-4]
            # Echo alternation A-B-A-B
            if L1 == L3 and L2 == L4 and L1 != L2:
                return 'BLACK' if L1 == 'RED' else 'RED'
            # 3-Streak Break Wave (A-A-A after B)
            if L1 == L2 == L3 and L4 != L1:
                return 'BLACK' if L1 == 'RED' else 'RED'

        L1, L2 = non_zero[-1], non_zero[-2]

        # Deep streak (cas >= 3) -> always fade opposite!
        if cas >= 3:
            return 'BLACK' if cac == 'RED' else 'RED'

        # Pair (cas == 2)
        if L1 == L2:
            mode = PrngDetectorMirror.detect_mode(history)
            zm = PrngDetectorMirror.get_zebra_momentum(history)
            
            # Saturated Alpha mean reversion: break pair if dominance >= 70%
            if L1 == alpha and top_r >= 0.70:
                return 'BLACK' if L1 == 'RED' else 'RED'

            if rule_id == 0:
                # v14.0 Baseline
                return L1
            elif rule_id == 1:
                # Rule 1: In Zebra mode, if fast alternation rate >= 0.60, fade pair!
                # In Transition or Danger, continue pair!
                fast_alt = PrngDetectorMirror.calc_alternation(non_zero[-6:]) if len(non_zero) >= 6 else 0.5
                if mode == 'ZEBRA' and fast_alt >= 0.60:
                    return 'BLACK' if L1 == 'RED' else 'RED'
                return L1
            elif rule_id == 2:
                # Rule 2: If strictly preceded by alternation (e.g. L3 != L2), fade pair unless in Danger mode!
                if mode != 'DANGER' and len(non_zero) >= 3 and non_zero[-3] != non_zero[-2]:
                    # was alternating before pair!
                    # only continue if Omega impulse (omega after long alpha streak)
                    return 'BLACK' if L1 == 'RED' else 'RED'
                return L1
            elif rule_id == 3:
                # Rule 3: Only continue pair if:
                # a) Danger mode, OR
                # b) Omega impulse (mean-reversion wave), OR
                # c) Doublet wave (A A B B)
                # If preceded by alternation in Zebra mode, fade!
                if mode == 'DANGER':
                    return L1
                if L1 == omega:
                    return L1
                if len(non_zero) >= 4 and non_zero[-3] == non_zero[-4]:
                    # Doublet wave (A A B B)
                    return L1
                # Otherwise, in alternation, fade pair!
                return 'BLACK' if L1 == 'RED' else 'RED'
            elif rule_id == 4:
                # Rule 4: Neutral pairs fade in Zebra; Alpha pairs fade if saturated (>= 68%); Omega continues
                if L1 == omega:
                    return L1
                if mode == 'ZEBRA':
                    return 'BLACK' if L1 == 'RED' else 'RED'
                return L1

        # Alternation (cas == 1)
        zm = PrngDetectorMirror.get_zebra_momentum(history)
        rec = L1 if zm['followL1'] else ('BLACK' if L1 == 'RED' else 'RED')
        if L1 == alpha and L2 == omega:
            osb = 0
            for i in range(len(non_zero) - 2, -1, -1):
                if non_zero[i] == omega:
                    osb += 1
                else:
                    break
            if osb >= 2:
                rec = alpha
        return rec

    return predict

def run_single_session(outs, pred_fn, cfg_fn, init_bank=4_040_371):
    bank = init_bank
    peak = bank
    max_dd = 0
    step = 1
    cdt = 0
    prev_bet = None
    mode = "ZEBRA"
    seq_start = "ZEBRA"
    seq_n = None
    zis = 0
    hist = []
    busted = False
    wins = nz_wins = tot_spins = tot_nz = 0
    cur_ls = max_ls = 0
    s_max_step = 1

    for o in outs:
        if bank < 1000:
            busted = True
            break
        tot_spins += 1
        is_nz = o != "ZERO"
        if is_nz:
            tot_nz += 1
        cycle_cap = bank + cdt
        z10 = sum(1 for x in hist[-10:] if x == "ZERO")
        zs = z10 >= 2 or zis >= 2
        locked = (
            (cdt > 0) and (not zs) and (cycle_cap >= 3_000_000) and (seq_start == "ZEBRA")
        )
        eff_mode = "ZEBRA" if locked else mode
        b0, mode_n = cfg_fn(eff_mode, cycle_cap)
        if cdt > 0 and seq_n is not None:
            eff_n = (
                min(10, max(seq_n, mode_n))
                if (zs and step >= 2)
                else min(mode_n, seq_n)
            )
        else:
            eff_n = mode_n

        bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
        if bet is None:
            busted = True
            break
        if step > s_max_step:
            s_max_step = step

        pred = pred_fn(hist)
        was_start = cdt == 0 or step == 1

        if o == "ZERO":
            net = -bet
            cdt += bet
            step += 1
            zis += 1
            cur_ls += 1
        elif o == pred:
            net = calc_net_win(bet)
            cdt = max(0, cdt - net)
            wins += 1
            nz_wins += 1
            cur_ls = 0
            if cdt == 0:
                step = 1
                zis = 0
        else:
            net = -bet
            cdt += bet
            step += 1
            cur_ls += 1
        max_ls = max(max_ls, cur_ls)
        bank += net
        if bank > peak:
            peak = bank
        max_dd = max(max_dd, peak - bank)
        hist.append(o)

        raw_m = PrngDetectorMirror.detect_mode(hist)
        z10_n = sum(1 for x in hist[-10:] if x == "ZERO")
        mode = "TRANSITION" if (z10_n >= 3 and raw_m == "ZEBRA") else raw_m

        if cdt == 0:
            seq_start = mode
            seq_n = None
            zis = 0
        elif was_start:
            seq_start = eff_mode
            seq_n = cfg_fn(eff_mode, cycle_cap)[1]
        else:
            z10_next = sum(1 for x in hist[-10:] if x == "ZERO")
            if (z10_next >= 2 or zis >= 2) and step >= 2:
                nxt_n = cfg_fn(mode, bank + cdt)[1]
                seq_n = min(10, max(seq_n if seq_n is not None else nxt_n, nxt_n))
        prev_bet = bet

    prof = bank - init_bank
    return {
        "prof": prof,
        "busted": busted,
        "max_dd": max_dd,
        "max_ls": max_ls,
        "max_step": s_max_step,
        "nz_wr": nz_wins / tot_nz * 100 if tot_nz else 0,
        "tot_spins": tot_spins,
    }

def run_suite(sessions, pred_fn, cfg_fn, init_bank):
    profs = []
    dds = []
    steps = []
    busted = 0
    sess_map = {}
    for name, outs in sessions:
        r = run_single_session(outs, pred_fn, cfg_fn, init_bank)
        profs.append(r["prof"])
        dds.append(r["max_dd"])
        steps.append(r["max_step"])
        if r["busted"]:
            busted += 1
        sess_map[name] = r
    return {
        "total_profit": sum(profs),
        "win_rate": sum(1 for p in profs if p > 0) / len(profs),
        "max_step": max(steps),
        "avg_max_step": sum(steps) / len(steps),
        "max_dd": max(dds),
        "busted": busted,
        "sess_map": sess_map,
    }

if __name__ == '__main__':
    sessions = load_clean()
    print(f'Testing Smart Pair Rules on {len(sessions)} clean sessions...\n')

    rules = [
        ('Rule 0: v14.0 Baseline', 0),
        ('Rule 1: Zebra + Alt>=0.60 -> Fade Pair', 1),
        ('Rule 2: Preceded by Alt (L3!=L2) -> Fade unless Danger', 2),
        ('Rule 3: Danger / Omega / Doublets continue, else Fade', 3),
        ('Rule 4: In Zebra Fade Neutral/Alpha, Omega continues', 4),
    ]

    for p_name, cfg, init_bank in [('TURBO_HARVEST', cfg_turbo, 4_000_000), ('APEX_IDEAL', cfg_apex, 3_800_000)]:
        print(f'--- {p_name} ({init_bank:,} RUB) ---')
        for label, rid in rules:
            p_fn = build_smart_pair_predictor(rule_id=rid, window=15)
            res = run_suite(sessions, p_fn, cfg, init_bank)
            
            n13 = next((v for k, v in res['sess_map'].items() if '2026-11-13' in k), None)
            n12 = next((v for k, v in res['sess_map'].items() if '2026-11-12' in k), None)
            n13_s = f"Nov13: +{n13['prof']:,} (st{n13['max_step']})" if n13 and n13['prof'] > 0 else f"Nov13: {n13['prof']:,}" if n13 else "Nov13: N/A"
            n12_s = f"Nov12: +{n12['prof']:,} (st{n12['max_step']})" if n12 and n12['prof'] > 0 else f"Nov12: {n12['prof']:,}" if n12 else "Nov12: N/A"

            print(f"{label:<55} | Net: {res['total_profit']:>10,d} ₽ | WinRate: {res['win_rate']:.1%} | MaxSt: {res['max_step']:2d} (avg {res['avg_max_step']:.1f}) | Busts: {res['busted']} | MaxDD: {res['max_dd']:>10,d} | {n13_s} | {n12_s}")
        print()
