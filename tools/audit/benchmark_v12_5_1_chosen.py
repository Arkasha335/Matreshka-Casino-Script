import os, sys, math
sys.path.append(os.path.dirname(__file__))
from benchmark_v12_5_1_strict_1m import TABLE_LIMIT, floor_win, geom_sum_factor, exact_bet_1m_floor, make_1m_cfg, run_bench_1m
from verify_final_v12_5_release import load_clean, gen_empirical, precompute_full

def make_turbo_v12_5_1(mode, cap):
    cap = max(10_000, cap)
    if cap >= 3_000_000:
        return make_1m_cfg((9000, 7), (5500, 8), (3000, 8))(mode, cap)
    return make_1m_cfg((6500, 8), (4500, 8), (2500, 8))(mode, cap)

p_shield_1251 = make_1m_cfg((1700, 10), (1200, 10), (1000, 10))
p_apex_1251   = make_1m_cfg((5000, 8),  (2500, 10), (1400, 10))
p_turbo_1251  = make_turbo_v12_5_1

if __name__ == '__main__':
    tr_real = precompute_full([x[1] for x in load_clean()])
    tr_mc100 = precompute_full(gen_empirical(2000, 100, 2026))
    tr_mc270 = precompute_full(gen_empirical(2000, 270, 7777))

    for name, fn, ncd, zlt in [
        ("SHIELD v12.5.1 (1.7/1.2/1.0, N10/10/10, Hysteresis)", p_shield_1251, False, None),
        ("APEX   v12.5.1 (5.0/2.5/1.4, N8/10/10,  Fast+ZL>=3M)", p_apex_1251,  True, 3_000_000),
        ("TURBO  v12.5.1 (<3M: 6.5/4.5/2.5 N8 | >=3M: 9/5.5/3 N7/8/8)", p_turbo_1251, True, 3_000_000),
    ]:
        print(f"\n=== {name} ===")
        for bank in [1_000_000, 2_000_000, 3_800_000, 6_500_000]:
            b0z, nz = fn('ZEBRA', bank)
            b0t, nt = fn('TRANSITION', bank)
            b0d, nd = fn('DANGER', bank)
            rr = run_bench_1m(tr_real, fn, bank, ncd, zlt, False)
            m1 = run_bench_1m(tr_mc100, fn, bank, ncd, zlt, False)
            m2 = run_bench_1m(tr_mc270, fn, bank, ncd, zlt, False)
            errs = rr['errs'] + m1['errs'] + m2['errs']
            print(f"  Bank={bank/1e6:3.1f}M ({b0z}/{b0t}/{b0d}, N{nz}/{nt}/{nd}) | R27:{rr['win']:>5.1f}% Med {rr['med']:>+9,.0f} P90 {rr['p90']:>+10,.0f} | MC100:{m1['win']:>5.1f}% {m1['med']:>+9,.0f} | 1h:{m2['win']:>5.1f}% Med {m2['med']:>+9,.0f} (Bust {m2['bust']:>4.1f}%) | Err={errs}")
