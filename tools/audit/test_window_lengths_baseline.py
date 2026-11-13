import sys
sys.path.insert(0, 'tools/audit')
from test_cas2_deep_study import load_clean
from benchmark_cas2_financials import run_single_session, cfg_turbo, cfg_apex
from grid_search_v15_architecture import build_v15_predictor, run_suite

sessions = load_clean()

print('=== TESTING WINDOW LENGTHS ON CLEAN SESSIONS (2,766 SPINS) ===\n')

windows = [10, 12, 14, 15, 16, 18, 20, 22, 25, 30]

for p_name, cfg, init_bank in [('APEX_IDEAL', cfg_apex, 3_800_000), ('TURBO_HARVEST', cfg_turbo, 4_000_000)]:
    print(f'--- Profile: {p_name} ({init_bank:,} RUB) ---')
    best_w = None
    best_prof = -999999999
    for w in windows:
        p_fn = build_v15_predictor(window=w, pair_alt_break=False, exp_guard=False, alpha_sat=0.70)
        res = run_suite(sessions, p_fn, cfg, init_bank)
        
        n13 = next((v for k, v in res['sess_map'].items() if '2026-11-13' in k), None)
        n12 = next((v for k, v in res['sess_map'].items() if '2026-11-12' in k), None)
        n11 = next((v for k, v in res['sess_map'].items() if '2026-11-11' in k), None)
        
        n13_s = f"Nov13: +{n13['prof']:,} (st{n13['max_step']})" if n13 and n13['prof'] > 0 else f"Nov13: {n13['prof']:,}" if n13 else "Nov13: N/A"
        n12_s = f"Nov12: +{n12['prof']:,} (st{n12['max_step']})" if n12 and n12['prof'] > 0 else f"Nov12: {n12['prof']:,}" if n12 else "Nov12: N/A"
        n11_s = f"Nov11: +{n11['prof']:,} (st{n11['max_step']})" if n11 and n11['prof'] > 0 else f"Nov11: {n11['prof']:,}" if n11 else "Nov11: N/A"

        print(f"Window W={w:2d} | Net: {res['total_profit']:>10,d} ₽ | WinRate: {res['win_rate']:.1%} | MaxSt: {res['max_step']:2d} (avg {res['avg_max_step']:.1f}) | Busts: {res['busted']} | MaxDD: {res['max_dd']:>10,d} | {n13_s} | {n12_s}")
    print()
