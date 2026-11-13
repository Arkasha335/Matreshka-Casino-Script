import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_mirror import PrngDetectorMirror
from parity_ts_vs_python import predict_v13
from research_v14_deep_audit import load_all_29

sessions = load_all_29()

# Let's inspect all 218 occurrences of АЛЬФА-ТРЕНД
alpha_trend_cases = []
for fn, outs in sessions:
    hist = []
    for o in outs:
        if not hist:
            hist.append(o)
            continue
        nz = [h for h in hist if h != "ZERO"]
        if len(nz) >= 2:
            L1 = nz[-1]
            L2 = nz[-2]
            res = PrngDetectorMirror.get_recommendation_and_confidence(hist)
            if res[2] == "АЛЬФА-ТРЕНД":
                alpha_trend_cases.append((fn, L1, L2, res[0], o))
        hist.append(o)

print(f"Total АЛЬФА-ТРЕНД cases: {len(alpha_trend_cases)}")
same_col = sum(1 for c in alpha_trend_cases if c[4] == c[1])  # actually continued
opp_col = sum(
    1 for c in alpha_trend_cases if c[4] not in (c[1], "ZERO")
)  # actually broke
zero_col = sum(1 for c in alpha_trend_cases if c[4] == "ZERO")
print(f"Actual outcome after L1==L2==Alpha:")
print(
    f"  Continued L1 ({alpha_trend_cases[0][1]}): {same_col} ({same_col/len(alpha_trend_cases)*100:.2f}%)"
)
print(
    f"  Broke to Opposite: {opp_col} ({opp_col/len(alpha_trend_cases)*100:.2f}%)"
)
print(
    f"  Zero: {zero_col} ({zero_col/len(alpha_trend_cases)*100:.2f}%)"
)
nz_tot = same_col + opp_col
print(
    f"  Non-Zero: Continued={same_col/nz_tot*100:.2f}% vs Broke={opp_col/nz_tot*100:.2f}%!"
)
