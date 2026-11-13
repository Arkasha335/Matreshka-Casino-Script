import os
import random
import statistics
import sys

sys.path.append(os.path.dirname(__file__))
from compare_v13_v14_detailed import pred_v14, run_single_session, cfg_apex, cfg_turbo
from parity_ts_vs_python import predict_v13

# Empirical parameters from all 2,711 spins:
# P(Zero) = 5.02%
# Non-zero: Red = 49.55%, Black = 50.45%
# Alternation rate: ~51%


def generate_markov_sessions(n_sessions=500, spins_per_session=200, seed=42):
    rng = random.Random(seed)
    sessions = []
    for _ in range(n_sessions):
        outs = []
        cur_col = "RED" if rng.random() < 0.5 else "BLACK"
        for _ in range(spins_per_session):
            u = rng.random()
            if u < 0.0502:
                outs.append("ZERO")
            else:
                # 51% alternation probability
                if rng.random() < 0.51:
                    cur_col = "BLACK" if cur_col == "RED" else "RED"
                outs.append(cur_col)
        sessions.append(outs)
    return sessions


mc_sessions = generate_markov_sessions(500, 200, seed=12345)
print(
    f"Generated {len(mc_sessions)} synthetic Markov sessions ({len(mc_sessions)*200:,} spins)"
)

# Test v13 vs v14 on APEX and TURBO
for prof_name, cfg_fn, init_b in [
    ("APEX @ 3.8M", cfg_apex, 3_800_000),
    ("TURBO @ 4.0M", cfg_turbo, 4_040_371),
]:
    print(f"\n=== Monte Carlo Stress: {prof_name} (500 Sessions x 200 Spins) ===")

    # v13
    v13_wins = v13_busts = 0
    v13_profs = []
    v13_dds = []
    for outs in mc_sessions:
        r = run_single_session(
            outs, lambda h: predict_v13(h, 15, 3), cfg_fn, init_b
        )
        if r["busted"]:
            v13_busts += 1
        elif r["prof"] > 0:
            v13_wins += 1
        v13_profs.append(r["prof"])
        v13_dds.append(r["max_dd"])

    # v14
    v14_wins = v14_busts = 0
    v14_profs = []
    v14_dds = []
    for outs in mc_sessions:
        r = run_single_session(outs, pred_v14, cfg_fn, init_b)
        if r["busted"]:
            v14_busts += 1
        elif r["prof"] > 0:
            v14_wins += 1
        v14_profs.append(r["prof"])
        v14_dds.append(r["max_dd"])

    print(
        f"  v13.0: Win Rate = {v13_wins/len(mc_sessions)*100:5.1f}% | Busts = {v13_busts/len(mc_sessions)*100:4.1f}% | Median Profit = {statistics.median(v13_profs):>+10,.0f} ₽ | MaxDD = {max(v13_dds):>9,d} ₽"
    )
    print(
        f"  v14.0: Win Rate = {v14_wins/len(mc_sessions)*100:5.1f}% | Busts = {v14_busts/len(mc_sessions)*100:4.1f}% | Median Profit = {statistics.median(v14_profs):>+10,.0f} ₽ | MaxDD = {max(v14_dds):>9,d} ₽"
    )
    delta_prof = statistics.median(v14_profs) - statistics.median(v13_profs)
    print(f"  Delta: WinRate +{(v14_wins - v13_wins)/len(mc_sessions)*100:.1f}%, Median Profit {delta_prof:>+10,.0f} ₽")
