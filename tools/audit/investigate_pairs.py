import os
import sys

sys.path.append(os.path.dirname(__file__))
from research_v14_deep_audit import load_all_29

sessions = load_all_29()

pairs_data = []

for fn, outs in sessions:
    nz = [h for h in outs if h != "ZERO"]
    for i in range(2, len(nz)):
        L1 = nz[i - 1]
        L2 = nz[i - 2]
        nxt = nz[i]
        if L1 == L2:
            # It's a pair!
            # What was before the pair? L3
            L3 = nz[i - 3] if i >= 3 else None
            L4 = nz[i - 4] if i >= 4 else None
            pairs_data.append((L1, L2, L3, L4, nxt))

print(f"Total pair instances (L1 == L2) in non-zero spins: {len(pairs_data)}")
cont = sum(1 for p in pairs_data if p[4] == p[0])
brk = sum(1 for p in pairs_data if p[4] != p[0])
print(
    f"Unconditional pair continuation: RRR/BBB = {cont} ({cont/len(pairs_data)*100:.2f}%) vs Break RRB/BBR = {brk} ({brk/len(pairs_data)*100:.2f}%)"
)

# Break down by L3:
# Case A: L3 == L1 (this was already a 3-streak L3=L2=L1, so L1==L2 was part of streak >= 3)
# Case B: L3 != L1 (exact pair of 2: X-Y-Y)
exact_pairs = [p for p in pairs_data if p[2] is not None and p[2] != p[0]]
print(f"\nExact isolated pairs (X-Y-Y, e.g. B-R-R or R-B-B): {len(exact_pairs)}")
ep_cont = sum(1 for p in exact_pairs if p[4] == p[0])
ep_brk = sum(1 for p in exact_pairs if p[4] != p[0])
print(
    f"  Continue to 3-streak (X-Y-Y-Y): {ep_cont} ({ep_cont/len(exact_pairs)*100:.2f}%)"
)
print(
    f"  Break to opposite (X-Y-Y-X):   {ep_brk} ({ep_brk/len(exact_pairs)*100:.2f}%)"
)

# What if L4=X, L3=X, L2=Y, L1=Y (Double pair: X-X-Y-Y)?
double_pairs = [
    p
    for p in pairs_data
    if p[3] is not None and p[3] == p[2] and p[2] != p[0] and p[1] == p[0]
]
print(
    f"\nDouble pairs (X-X-Y-Y, e.g. B-B-R-R or R-R-B-B): {len(double_pairs)}"
)
dp_cont = sum(1 for p in double_pairs if p[4] == p[0])  # XXYYY
dp_brk = sum(1 for p in double_pairs if p[4] != p[0])  # XXYYX
print(
    f"  Continue to XXYYY: {dp_cont} ({dp_cont/len(double_pairs)*100:.2f}%)"
)
print(
    f"  Break to XXYYX (pair flip): {dp_brk} ({dp_brk/len(double_pairs)*100:.2f}%)"
)
