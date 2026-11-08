import json
import math
import sys
import numpy as np

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Normal CDF for p-values
def normal_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def normal_p_value_two_tailed(z):
    return 2.0 * (1.0 - normal_cdf(abs(z)))

def chi2_p_value_df1(chi2_stat):
    # For df=1, chi2 = z^2
    z = math.sqrt(max(0.0, chi2_stat))
    return normal_p_value_two_tailed(z)

def chi2_p_value_approx(chi2_stat, df):
    # Wilson-Hilferty approximation for Chi-Square CDF
    if df <= 0 or chi2_stat <= 0:
        return 1.0
    s = math.sqrt(2.0 / (9.0 * df))
    z = ((chi2_stat / df) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / s
    p = 1.0 - normal_cdf(z)
    return max(0.0, min(1.0, p))

with open(r"D:\Projects\MTCasinoScript\tools\audit\normalized_spins.json", "r", encoding="utf-8") as f:
    spins = json.load(f)

N = len(spins)
print(f"================================================================================")
print(f"      REVERSE-ENGINEERING PRNG & STOCHASTIC AUDIT REPORT (N = {N} SPINS)        ")
print(f"================================================================================\n")

# 1. FREQUENCY ANALYSIS
outcomes = [s["outcome"] for s in spins]
red_cnt = outcomes.count("RED")
black_cnt = outcomes.count("BLACK")
zero_cnt = outcomes.count("ZERO")

p_red_emp = red_cnt / N
p_black_emp = black_cnt / N
p_zero_emp = zero_cnt / N

# Theoretical European Roulette
p_red_theo = 18.0 / 37.0
p_black_theo = 18.0 / 37.0
p_zero_theo = 1.0 / 37.0

e_red = N * p_red_theo
e_black = N * p_black_theo
e_zero = N * p_zero_theo

chi2_freq = ((red_cnt - e_red)**2 / e_red) + ((black_cnt - e_black)**2 / e_black) + ((zero_cnt - e_zero)**2 / e_zero)
p_val_freq = chi2_p_value_approx(chi2_freq, df=2)

# Z-scores
z_red = (red_cnt - e_red) / math.sqrt(N * p_red_theo * (1 - p_red_theo))
z_black = (black_cnt - e_black) / math.sqrt(N * p_black_theo * (1 - p_black_theo))
z_zero = (zero_cnt - e_zero) / math.sqrt(N * p_zero_theo * (1 - p_zero_theo))

print("1. FREQUENCY ANALYSIS (vs European Roulette 18/37 - 18/37 - 1/37):")
print(f"  RED:   {red_cnt:4d} ({p_red_emp*100:6.2f}%)  [Theoretical: {e_red:6.1f} ({p_red_theo*100:5.2f}%), Z = {z_red:+6.2f}, p = {normal_p_value_two_tailed(z_red):.4f}]")
print(f"  BLACK: {black_cnt:4d} ({p_black_emp*100:6.2f}%)  [Theoretical: {e_black:6.1f} ({p_black_theo*100:5.2f}%), Z = {z_black:+6.2f}, p = {normal_p_value_two_tailed(z_black):.4f}]")
print(f"  ZERO:  {zero_cnt:4d} ({p_zero_emp*100:6.2f}%)  [Theoretical: {e_zero:6.1f} ({p_zero_theo*100:5.2f}%), Z = {z_zero:+6.2f}, p = {normal_p_value_two_tailed(z_zero):.4f}]")
print(f"  Chi-Square Goodness-of-Fit: chi2 = {chi2_freq:.3f}, df = 2, p-value = {p_val_freq:.4f}")
if p_val_freq < 0.05:
    print("  --> STATISTICALLY SIGNIFICANT DEVIATION from European Roulette at alpha=0.05!")
else:
    print("  --> Frequency distribution does NOT show significant global deviation at alpha=0.05.")

# Ratio RED to BLACK (excluding ZERO)
non_zero = [o for o in outcomes if o != "ZERO"]
N_nz = len(non_zero)
n_red = non_zero.count("RED")
n_black = non_zero.count("BLACK")
z_rb = (n_red - n_black) / math.sqrt(N_nz)
print(f"  Red vs Black ratio: {n_red}/{n_black} = {n_red/n_black:.3f} (Z = {z_rb:+.2f}, p = {normal_p_value_two_tailed(z_rb):.4f})\n")

# 2. RUNS TEST (WALD-WOLFOWITZ)
runs = 1
for i in range(1, len(non_zero)):
    if non_zero[i] != non_zero[i-1]:
        runs += 1

mu_runs = 1.0 + (2.0 * n_red * n_black) / N_nz
var_runs = (2.0 * n_red * n_black * (2.0 * n_red * n_black - N_nz)) / (N_nz**2 * (N_nz - 1.0))
sigma_runs = math.sqrt(var_runs)
z_runs = (runs - mu_runs) / sigma_runs
p_val_runs = normal_p_value_two_tailed(z_runs)

print("2. WALD-WOLFOWITZ RUNS TEST (Randomness of Sequence):")
print(f"  Non-zero spins: {N_nz} (n1 = {n_red}, n2 = {n_black})")
print(f"  Observed Runs (R): {runs}")
print(f"  Expected Runs (E[R]): {mu_runs:.2f}")
print(f"  Variance (Var[R]): {var_runs:.2f} (StdDev: {sigma_runs:.2f})")
print(f"  Z-score: {z_runs:+.3f}")
print(f"  Two-tailed p-value: {p_val_runs:.4f}")
if p_val_runs < 0.05:
    print("  --> HYPOTHESIS OF INDEPENDENCE REJECTED! Runs count is non-random.")
    if z_runs < 0:
        print("  --> Negative Z indicates CLUSTERING / PERSISTENT STREAKS (significantly fewer runs than fair PRNG)!")
    else:
        print("  --> Positive Z indicates EXCESSIVE ALTERNATION (sawtooth/zebra pattern)!")
else:
    print("  --> Runs test does not reject global independence at alpha=0.05.")

# 3. STREAK LENGTH DISTRIBUTION ANALYSIS
print("\n3. STREAK LENGTH DISTRIBUTION (Non-zero sequences):")
streak_lengths = []
curr_len = 1
for i in range(1, len(non_zero)):
    if non_zero[i] == non_zero[i-1]:
        curr_len += 1
    else:
        streak_lengths.append((non_zero[i-1], curr_len))
        curr_len = 1
streak_lengths.append((non_zero[-1], curr_len))

total_streaks = len(streak_lengths)
print(f"  Total individual streaks: {total_streaks}")
print(f"  Mean streak length: {np.mean([l for c, l in streak_lengths]):.2f} (Theoretical for fair coin: 2.00)")
print(f"  Max streak length observed: {max(l for c, l in streak_lengths)}")

streak_counts = {}
for c, l in streak_lengths:
    streak_counts[l] = streak_counts.get(l, 0) + 1

print("\n  Streak Length Breakdown:")
print(f"  Len | Observed | Expected (p=0.5) | Ratio (Obs/Exp)")
print(f"  ----+----------+------------------+----------------")
chi2_streak = 0.0
for k in range(1, 11):
    obs = streak_counts.get(k, 0)
    exp = total_streaks * (0.5 ** k)
    ratio = obs / exp if exp > 0 else 0
    print(f"  {k:2d}  | {obs:8d} | {exp:16.1f} | {ratio:15.2f}")

streaks_7plus = sum(streak_counts.get(k, 0) for k in streak_counts if k >= 7)
exp_7plus = total_streaks * sum(0.5 ** k for k in range(7, 30))
print(f"  Streaks >= 7: Observed = {streaks_7plus}, Expected = {exp_7plus:.1f} (Ratio = {streaks_7plus/exp_7plus if exp_7plus>0 else 0:.2f})")

# 4. AUTOCORRELATION ANALYSIS (Lags 1 to 15)
print("\n4. AUTOCORRELATION OF OUTCOMES (Red = +1, Black = -1):")
numeric_outcomes = np.array([1 if o == "RED" else -1 for o in non_zero])
numeric_mean = np.mean(numeric_outcomes)
numeric_var = np.var(numeric_outcomes)
bartlett_band = 1.96 / math.sqrt(len(numeric_outcomes))
print(f"  Bartlett 95% White-Noise Band: +/- {bartlett_band:.3f}")

for lag in range(1, 16):
    cov = np.mean((numeric_outcomes[:-lag] - numeric_mean) * (numeric_outcomes[lag:] - numeric_mean))
    r_k = cov / numeric_var
    sig = "*" if abs(r_k) > bartlett_band else " "
    print(f"  Lag {lag:2d}: r = {r_k:+6.3f} {sig}")

# 5. CONDITIONAL PROBABILITY ANALYSIS: P(Zero | Bet Size)
print("\n5. CONDITIONAL ZERO PROBABILITY P(Zero | Bet Size):")
# Segment spins by bet size
base_spins = [s for s in spins if s["bet"] <= 4000]
mid_spins = [s for s in spins if 4000 < s["bet"] <= 25000]
high_spins = [s for s in spins if s["bet"] > 25000]

def zero_stats(subset, label):
    if not subset:
        return
    n = len(subset)
    z = sum(1 for s in subset if s["outcome"] == "ZERO")
    p_emp = z / n
    # Z-score vs theoretical 1/37 (0.02703)
    p_theo = 1.0 / 37.0
    se = math.sqrt(p_theo * (1.0 - p_theo) / n)
    z_score = (p_emp - p_theo) / se if se > 0 else 0
    p_val = normal_p_value_two_tailed(z_score)
    print(f"  {label:25s}: N = {n:4d}, Zero = {z:2d} ({p_emp*100:5.2f}%) [Theoretical: {p_theo*100:.2f}%, Z = {z_score:+5.2f}, p = {p_val:.4f}]")

zero_stats(base_spins, "Base Bets (<= 4,000 ₽)")
zero_stats(mid_spins, "Mid Bets (4k - 25k ₽)")
zero_stats(high_spins, "High Bets (> 25k ₽)")

# By step number
print("\n  Zero Probability by Martingale Step:")
for step in range(1, 9):
    step_subset = [s for s in spins if s["step"] == step]
    if step_subset:
        zero_stats(step_subset, f"Step {step}")

# 6. PLAYER WINRATE BY MARTINGALE STEP (Dynamic Draining Hypothesis)
print("\n6. EMPIRICAL WINRATE BY MARTINGALE STEP:")
print(f"  Theoretical winrate for fair roulette: {18/37*100:.2f}%")
for step in range(1, 9):
    step_spins = [s for s in spins if s["step"] == step]
    if not step_spins:
        continue
    n = len(step_spins)
    wins = sum(1 for s in step_spins if s["is_win"])
    wr = wins / n
    p_theo = 18.0 / 37.0
    se = math.sqrt(p_theo * (1.0 - p_theo) / n)
    z_score = (wr - p_theo) / se if se > 0 else 0
    p_val = normal_p_value_two_tailed(z_score)
    print(f"  Step {step}: N = {n:3d}, Wins = {wins:3d}, Winrate = {wr*100:5.1f}% (Z = {z_score:+5.2f}, p = {p_val:.4f})")

# 7. CONDITIONAL PROBABILITY: P(Streak Breaks | Streak Length k)
print("\n7. PROBABILITY OF FLIP P(Flip | Current Streak Length = k):")
print("  k | Total At Len k | Flips (Break) | P(Flip) | Theoretical (0.50)")
print("----+----------------+---------------+---------+-------------------")
# Calculate from non_zero sequence
for k in range(1, 9):
    total_at_k = 0
    flips_at_k = 0
    curr = 1
    for i in range(1, len(non_zero)):
        if non_zero[i] == non_zero[i-1]:
            curr += 1
            if curr == k:
                total_at_k += 1
        else:
            if curr == k:
                flips_at_k += 1
            curr = 1
    if total_at_k + flips_at_k > 0:
        total_trials = total_at_k + flips_at_k
        p_flip = flips_at_k / total_trials
        print(f"  {k:1d} | {total_trials:14d} | {flips_at_k:13d} | {p_flip*100:6.1f}% | 50.0%")
