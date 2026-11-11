import os, sys, math
sys.path.append(os.path.dirname(__file__))
from verify_final_v12_5_release import run_bench, load_clean, gen_empirical, precompute_full, exact_solver_bet

def geom_sum_factor(n, x=2.025):
    return (math.pow(x, n) - 1.0) / (x - 1.0)

def make_capped_preset(z_spec, t_spec, d_spec):
    specs = {'ZEBRA': z_spec, 'TRANSITION': t_spec, 'DANGER': d_spec}
    def fn(mode, cap, limit):
        cap = max(10_000, cap)
        limit = max(10_000, limit)
        scale = max(0.15, min(limit, cap / 1.92) / 1_000_000.0)
        b0, n = specs[mode]
        while n > 5 and 1000 * geom_sum_factor(n) > cap:
            n -= 1
        max_b0_budget = max(1000, int(math.floor(cap / geom_sum_factor(n) / 100.0) * 100))
        scaled_b0 = max(1000, min(limit, max_b0_budget, int(round(b0 * scale / 100.0) * 100)))
        return scaled_b0, n
    return fn

p_shield = make_capped_preset((1700,10),(1200,10),(1000,10))
p_apex   = make_capped_preset((3500,9), (2000,10),(1200,10))
p_turbo  = make_capped_preset((6000,8), (4000,8), (1700,9))

if __name__ == '__main__':
    tr_real = precompute_full([x[1] for x in load_clean()])
    tr_mc100 = precompute_full(gen_empirical(2000, 100, 2026))
    tr_mc270 = precompute_full(gen_empirical(2000, 270, 7777))

    for name, fn, ncd, zlt in [
        ("SHIELD (1.7/1.2/1.0, 10/10/10)", p_shield, False, None),
        ("APEX   (3.5/2.0/1.2, 9/10/10)",  p_apex,   True, 3_000_000),
        ("TURBO  (6.0/4.0/1.7, 8/8/9)",    p_turbo,  True, 3_000_000),
    ]:
        print(f"\n=== {name} ===")
        for lim in [1_000_000, 2_000_000]:
            for bank in ([1_000_000, 2_000_000, 3_800_000, 6_500_000] if lim == 1_000_000 else [2_000_000, 3_800_000, 6_500_000]):
                rr = run_bench(tr_real, fn, bank, lim, ncd, zlt, False)
                m1 = run_bench(tr_mc100, fn, bank, lim, ncd, zlt, False)
                m2 = run_bench(tr_mc270, fn, bank, lim, ncd, zlt, False)
                print(f"  M={lim//1_000_000}M Bank={bank/1e6:3.1f}M | B0_Z={fn('ZEBRA',bank,lim)[0]:>5,d}/N{fn('ZEBRA',bank,lim)[1]} | R27:{rr['win']:>5.1f}% {rr['med']:>+9,.0f} (P90 {rr['p90']:>+10,.0f}) | MC100:{m1['win']:>5.1f}% {m1['med']:>+9,.0f} | 1h:{m2['win']:>5.1f}% {m2['med']:>+9,.0f} (Bust {m2['bust']:>4.1f}%)")
