import sys
sys.path.insert(0, 'tools/audit')
from test_cas2_deep_study import load_clean, get_matrix
from benchmark_cas2_financials import run_single_session, cfg_turbo, cfg_apex
from grid_search_v15_architecture import run_suite
from engine_mirror import PrngDetectorMirror

sessions = load_clean()

def build_v15_refined_predictor(window=20, alpha_sat=0.70, alpha_threshold=0.55, pair_step_guard=False):
    def predict(history):
        if not history:
            return 'RED'
        non_zero = [h for h in history if h != 'ZERO']
        if len(non_zero) < 2:
            return non_zero[-1] if non_zero else 'RED'

        # Multi-scale: Macro window for Alpha/Omega & Expectancy, Micro window for Alternation
        win_nz = non_zero[-window:]
        tot = len(win_nz)
        rc = win_nz.count('RED')
        bc = win_nz.count('BLACK')
        r_r = rc / tot
        b_r = bc / tot
        
        alpha = 'RED' if r_r > alpha_threshold else ('BLACK' if b_r > alpha_threshold else 'NEUTRAL')
        omega = 'BLACK' if alpha == 'RED' else ('RED' if alpha == 'BLACK' else 'NEUTRAL')
        top_r = max(r_r, b_r)
        
        cas = 0
        cac = non_zero[-1]
        for h in reversed(non_zero):
            if h == cac:
                cas += 1
            else:
                break

        # MPD patterns (4 spins)
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
            # Saturated Alpha mean reversion: break pair if dominance >= alpha_sat
            if L1 == alpha and top_r >= alpha_sat:
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

if __name__ == '__main__':
    print('=== REFINED v15 ENGINE PARAMETER STUDY (30 SESSIONS) ===\n')

    candidates = [
        ('v14.0 Baseline (W=15, Sat=0.70, Ath=0.55)', 15, 0.70, 0.55),
        ('v15-C1 (W=20, Sat=0.70, Ath=0.55)', 20, 0.70, 0.55),
        ('v15-C2 (W=22, Sat=0.70, Ath=0.55)', 22, 0.70, 0.55),
        ('v15-C3 (W=24, Sat=0.70, Ath=0.55)', 24, 0.70, 0.55),
        ('v15-C4 (W=25, Sat=0.70, Ath=0.55)', 25, 0.70, 0.55),
        ('v15-C5 (W=20, Sat=0.68, Ath=0.55)', 20, 0.68, 0.55),
        ('v15-C6 (W=20, Sat=0.70, Ath=0.58)', 20, 0.70, 0.58),
        ('v15-C7 (W=25, Sat=0.68, Ath=0.55)', 25, 0.68, 0.55),
        ('v15-C8 (W=25, Sat=0.70, Ath=0.58)', 25, 0.70, 0.58),
    ]

    for p_name, cfg, init_bank in [('APEX_IDEAL', cfg_apex, 3_800_000), ('TURBO_HARVEST', cfg_turbo, 4_000_000)]:
        print(f'--- {p_name} ({init_bank:,} RUB) ---')
        for label, w, sat, ath in candidates:
            p_fn = build_v15_refined_predictor(window=w, alpha_sat=sat, alpha_threshold=ath)
            res = run_suite(sessions, p_fn, cfg, init_bank)
            
            n13 = next((v for k, v in res['sess_map'].items() if '2026-11-13' in k), None)
            n12 = next((v for k, v in res['sess_map'].items() if '2026-11-12' in k), None)
            n13_s = f"Nov13: +{n13['prof']:,} (st{n13['max_step']})" if n13 and n13['prof'] > 0 else f"Nov13: {n13['prof']:,}" if n13 else "Nov13: N/A"
            n12_s = f"Nov12: +{n12['prof']:,} (st{n12['max_step']})" if n12 and n12['prof'] > 0 else f"Nov12: {n12['prof']:,}" if n12 else "Nov12: N/A"

            print(f"{label:<48} | Net: {res['total_profit']:>10,d} ₽ | WinRate: {res['win_rate']:.1%} | MaxSt: {res['max_step']:2d} (avg {res['avg_max_step']:.1f}) | Busts: {res['busted']} | MaxDD: {res['max_dd']:>10,d} | {n13_s} | {n12_s}")
        print()
