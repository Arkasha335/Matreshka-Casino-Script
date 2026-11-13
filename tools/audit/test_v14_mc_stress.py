import os
import random
import sys

sys.path.append(os.path.dirname(__file__))
from test_v14_antitunnel_bench import run_causal_v14, cfg_apex, cfg_turbo

def gen_mc(n_sess, n_spins, p_zero, seed):
    rng = random.Random(seed)
    p_col = (1.0 - p_zero) * 0.5
    return [
        [
            "ZERO" if (u := rng.random()) < p_zero else ("RED" if u < p_zero + p_col else "BLACK")
            for _ in range(n_spins)
        ]
        for _ in range(n_sess)
    ]

mc5 = gen_mc(1000, 270, 0.0502, 9999)

print("=== 1,000 MC 1-HOUR (270 SPINS, 5.02% ZERO) COMPARISON ===")
for name, rev_lim in [("v13 Standard", 99), ("v14 Anti-Tunnel (cas>=5)", 5)]:
    print(f"\n--- {name} ---")
    ra = run_causal_v14(mc5, cfg_apex, 3_800_000, True, 3_000_000, True, rev_lim)
    rt = run_causal_v14(mc5, cfg_turbo, 4_040_371, True, 3_000_000, True, rev_lim)
    print(f"  APEX  @ 3.8M: Win={ra['win']:5.1f}% | Med={ra['med']:>+9,.0f}/h | Bust={ra['bust']:4.1f}%")
    print(f"  TURBO @ 4.0M: Win={rt['win']:5.1f}% | Med={rt['med']:>+9,.0f}/h | Bust={rt['bust']:4.1f}%")
