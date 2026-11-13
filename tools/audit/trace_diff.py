import sys
sys.path.insert(0, 'tools/audit')
from test_cas2_deep_study import load_clean
from grid_search_v15_architecture import build_v15_predictor, run_suite, cfg_apex

sessions = load_clean()
p_v14 = build_v15_predictor(window=15, pair_alt_break=False, exp_guard=False, alpha_sat=0.70)
p_g2 = build_v15_predictor(window=15, pair_alt_break=True, exp_guard=True, alpha_sat=0.70)

res14 = run_suite(sessions, p_v14, cfg_apex, 3_800_000)
res_g2 = run_suite(sessions, p_g2, cfg_apex, 3_800_000)

print('=== SESSION COMPARISON: v14.0 vs G2 (APEX 3.8M) ===')
for name, outs in sessions:
    r14 = res14['sess_map'][name]
    rg2 = res_g2['sess_map'][name]
    diff = rg2['prof'] - r14['prof']
    if abs(diff) > 50_000 or rg2['busted'] != r14['busted']:
        print(f"{name:<45} | v14: {r14['prof']:>9,d} (st{r14['max_step']}) | G2: {rg2['prof']:>9,d} (st{rg2['max_step']}) | Diff: {diff:>10,d} | Busted: v14={r14['busted']}, G2={rg2['busted']}")
