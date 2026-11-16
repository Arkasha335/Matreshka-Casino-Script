import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, simulate_session, predict_v15_1, predict_v15_2, get_cfg_v15_1_2

sessions = load_all_unique_sessions()
print(f"Comparing 15.1 vs 15.2 per session (Sessions with differences):")
diff_count = 0
for s in sessions:
    r1 = simulate_session(s['outcomes'], predict_v15_1, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL')
    r2 = simulate_session(s['outcomes'], predict_v15_2, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL')
    if r1['resets'] != r2['resets'] or abs(r1['net_profit'] - r2['net_profit']) > 100000:
        diff_count += 1
        fn = s['file']
        print(f"{fn:<38} | 15.1: Net={r1['net_profit']:>+11,.0f} ₽, WR={r1['wr']:>5.1f}%, Res={r1['resets']} | 15.2: Net={r2['net_profit']:>+11,.0f} ₽, WR={r2['wr']:>5.1f}%, Res={r2['resets']}")
