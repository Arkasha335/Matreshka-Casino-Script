import sys
sys.path.insert(0, 'tools/audit')
from test_cas2_deep_study import load_clean
from benchmark_cas2_financials import cfg_turbo, cfg_apex
from grid_search_v15_architecture import run_suite
from engine_mirror import PrngDetectorMirror

sessions = load_clean()

def build_w24_variant(alt_break_mode=0):
    def predict(history):
        if not history:
            return 'RED'
        non_zero = [h for h in history if h != 'ZERO']
        if len(non_zero) < 2:
            return non_zero[-1] if non_zero else 'RED'

        window = 24
        win_nz = non_zero[-window:]
        tot = len(win_nz)
        rc = win_nz.count('RED')
        bc = win_nz.count('BLACK')
        r_r = rc / tot
        b_r = bc / tot
        
        alpha = 'RED' if r_r > 0.55 else ('BLACK' if b_r > 0.55 else 'NEUTRAL')
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
            # Saturated Alpha mean reversion: break pair if dominance >= 70%
            if L1 == alpha and top_r >= 0.70:
                return 'BLACK' if L1 == 'RED' else 'RED'

            if alt_break_mode == 0:
                # W=24 baseline: continue pair
                return L1
            elif alt_break_mode == 1:
                # Fade only if strictly alternating for at least 4 spins (A B A B B)
                if len(non_zero) >= 5:
                    if non_zero[-1] == non_zero[-2] and non_zero[-2] != non_zero[-3] and non_zero[-3] != non_zero[-4] and non_zero[-4] != non_zero[-5]:
                        return 'BLACK' if L1 == 'RED' else 'RED'
                return L1
            elif alt_break_mode == 2:
                # Fade only if strictly alternating for at least 3 spins (B A B B)
                if len(non_zero) >= 4:
                    if non_zero[-1] == non_zero[-2] and non_zero[-2] != non_zero[-3] and non_zero[-3] != non_zero[-4]:
                        return 'BLACK' if L1 == 'RED' else 'RED'
                return L1
            elif alt_break_mode == 3:
                # Saturated Alpha at 0.67 instead of 0.70
                if L1 == alpha and top_r >= 0.67:
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
    print('=== TESTING W=24 PAIR REFINEMENTS ===\n')

    variants = [
        ('W=24 Baseline (Hold Pair)', 0),
        ('W=24 AltDepth 4 Fade (A B A B B -> Fade)', 1),
        ('W=24 AltDepth 3 Fade (B A B B -> Fade)', 2),
        ('W=24 Saturation 67% Fade', 3),
    ]

    for p_name, cfg, init_bank in [('APEX_IDEAL', cfg_apex, 3_800_000), ('TURBO_HARVEST', cfg_turbo, 4_000_000)]:
        print(f'--- {p_name} ({init_bank:,} RUB) ---')
        for label, m in variants:
            p_fn = build_w24_variant(m)
            res = run_suite(sessions, p_fn, cfg, init_bank)
            
            n13 = next((v for k, v in res['sess_map'].items() if '2026-11-13' in k), None)
            n12 = next((v for k, v in res['sess_map'].items() if '2026-11-12' in k), None)
            n13_s = f"Nov13: +{n13['prof']:,} (st{n13['max_step']})" if n13 and n13['prof'] > 0 else f"Nov13: {n13['prof']:,}" if n13 else "Nov13: N/A"
            n12_s = f"Nov12: +{n12['prof']:,} (st{n12['max_step']})" if n12 and n12['prof'] > 0 else f"Nov12: {n12['prof']:,}" if n12 else "Nov12: N/A"

            print(f"{label:<42} | Net: {res['total_profit']:>10,d} ₽ | WinRate: {res['win_rate']:.1%} | MaxSt: {res['max_step']:2d} (avg {res['avg_max_step']:.1f}) | Busts: {res['busted']} | MaxDD: {res['max_dd']:>10,d} | {n13_s} | {n12_s}")
        print()
