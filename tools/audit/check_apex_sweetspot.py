import os, sys
sys.path.append(os.path.dirname(__file__))
from verify_final_v12_5_release import make_universal_preset, run_bench, load_clean, gen_empirical, precompute_full

tr_real = precompute_full([x[1] for x in load_clean()])
tr_mc100 = precompute_full(gen_empirical(2000, 100, 2026))
tr_mc270 = precompute_full(gen_empirical(2000, 270, 7777))

cands = [
    ("SHIELD (1.7/1.2/1.0, 10/10/10)",        make_universal_preset((1700,10),(1200,10),(1000,10), 9), False, None, True),
    ("APEX_A (3.0/1.5/1.0, 9/10/10, minN)",   make_universal_preset((3000,9), (1500,10),(1000,10), 9), True, 3_000_000, False),
    ("APEX_X1(3.5/2.0/1.2, 9/10/10, minN)",   make_universal_preset((3500,9), (2000,10),(1200,10), 9), True, 3_000_000, False),
    ("APEX_X2(4.0/2.0/1.2, 9/10/10, minN)",   make_universal_preset((4000,9), (2000,10),(1200,10), 9), True, 3_000_000, False),
    ("APEX_C (3.5/2.0/1.2, 9/9/10, minN)",    make_universal_preset((3500,9), (2000,9), (1200,10), 9), True, 3_000_000, False),
    ("APEX_Z8(5.0/2.5/1.4, 8/10/10, minN)",   make_universal_preset((5000,8), (2500,10),(1400,10), 8), True, 3_000_000, False),
    ("TURBO_A(6.0/4.0/1.7, 8/8/9, minN)",     make_universal_preset((6000,8), (4000,8), (1700,9),  8), True, 3_000_000, False),
]

for lim, banks in [(1_000_000, [2_000_000, 6_500_000]), (2_000_000, [2_000_000, 3_800_000, 6_500_000])]:
    for b_init in banks:
        print(f"\n--- M={lim:,} | Bank={b_init:,} ---")
        for lbl, fn, ncd, zlt, lsn in cands:
            rr = run_bench(tr_real, fn, b_init, lim, ncd, zlt, lsn)
            m1 = run_bench(tr_mc100, fn, b_init, lim, ncd, zlt, lsn)
            m2 = run_bench(tr_mc270, fn, b_init, lim, ncd, zlt, lsn)
            print(f"{lbl:<34} | R27:{rr['win']:>5.1f}% {rr['med']:>+8,.0f} (P90 {rr['p90']:>+9,.0f}) | MC100:{m1['win']:>5.1f}% {m1['med']:>+8,.0f} | 1h:{m2['win']:>5.1f}% {m2['med']:>+8,.0f} (Bust {m2['bust']:>4.1f}%)")
