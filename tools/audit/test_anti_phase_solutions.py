"""
Test Anti-Phase Solutions & High-Step Safety Policies across all 49 sessions.
Simulates financial execution under APEX_IDEAL (Bankroll = 7.5M ₽).
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions, get_cfg_v15_1_2, simulate_session
from engine_mirror import PrngDetectorMirror, BankrollManagerMirror

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

# Build v16.1 Purified Feature Model
from test_v16_1_purified_features import extract_features_v16_1_purified
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

print("Training v16.1 Purified Model on all sessions...")
X_list, y_list = [], []
for sess in sessions:
    hist = []
    for out in sess['outcomes']:
        if out in ('RED', 'BLACK') and len(hist) >= 4:
            f = extract_features_v16_1_purified(hist)
            if f:
                X_list.append(f)
                y_list.append(1 if out == 'RED' else 0)
        hist.append(out)

X = np.array(X_list, dtype=np.float32)
y = np.array(y_list, dtype=np.int32)

sc = StandardScaler()
X_scaled = sc.fit_transform(X)
clf = MLPClassifier(hidden_layer_sizes=(24, 12), activation='tanh', alpha=0.15, max_iter=300, random_state=42)
clf.fit(X_scaled, y)
print(f"v16.1 Model trained (iterations: {clf.n_iter_}, in-sample acc: {clf.score(X_scaled, y)*100:.2f}%)")

def predict_v16_0(hist):
    r, _, _ = PrngDetectorMirror.get_recommendation_and_confidence(hist)
    return r

def predict_v16_1_baseline(hist):
    if not hist: return 'RED'
    raw = [h if isinstance(h, str) else h.get('outcome', '') for h in hist]
    nz = [x for x in raw if x != 'ZERO']
    if len(nz) < 3: return nz[-1] if nz else 'RED'
    
    feats = extract_features_v16_1_purified(raw)
    if feats:
        zf = sc.transform([feats])
        p_red = clf.predict_proba(zf)[0, 1]
        if abs(p_red - 0.5) >= 0.06:
            return 'RED' if p_red >= 0.5 else 'BLACK'
            
    # Purified Streak-Mood Fallback
    cur_col = nz[-1]
    opp_col = 'BLACK' if cur_col == 'RED' else 'RED'
    s = PrngDetectorMirror.calc_current_streak(nz)
    
    # Previous streak
    prev_s = 1
    idx_prev = len(nz) - 1 - s
    if idx_prev >= 0:
        for k in range(idx_prev - 1, -1, -1):
            if nz[k] == opp_col: prev_s += 1
            else: break
            
    # Rolling average streak for cur_col in last 24
    w24 = nz[-24:]
    st_c = []
    if w24:
        tc = w24[0]; tl = 1
        for j in range(1, len(w24)):
            if w24[j] == tc: tl += 1
            else:
                if tc == cur_col: st_c.append(tl)
                tc = w24[j]; tl = 1
        if tc == cur_col: st_c.append(tl)
    avg_cur = sum(st_c)/len(st_c) if st_c else 1.8
    
    # Streak == 1: Single
    if s == 1:
        # If prev was single, strong alternation tendency
        if prev_s == 1: return opp_col
        # If prev was pair and avg_cur >= 1.8: couplet tendency
        if prev_s == 2 and avg_cur >= 1.8: return cur_col
        return opp_col
        
    # Streak == 2: Pair (The crucial fix!)
    if s == 2:
        # If prev was also a pair (2-2 pattern), BREAK PAIR!
        if prev_s == 2: return opp_col
        # If current color is averaging short series (<1.95), BREAK PAIR!
        if avg_cur < 1.95: return opp_col
        # Only continue to 3 if prev was deep or avg is long
        if prev_s >= 3 or avg_cur >= 2.2: return cur_col
        # Default in neutral: BREAK PAIR (52.2% break rate)
        return opp_col
        
    # Streak >= 3: Deep streak
    # Fading against deep streaks with saturation check
    return opp_col

# Solution 3: v16.1 with Step-Adaptive Confidence & Anti-Phase Breaker
def make_v16_1_step_adaptive(step_policy='trend_anchor'):
    def predict_adaptive(hist, current_step=1):
        if not hist: return 'RED'
        raw = [h if isinstance(h, str) else h.get('outcome', '') for h in hist]
        nz = [x for x in raw if x != 'ZERO']
        if len(nz) < 3: return nz[-1] if nz else 'RED'
        
        # At Step >= 4, check Anti-Phase Breaker
        if current_step >= 4:
            if step_policy == 'follow_last':
                # Follow the color that just hit: eliminates streak vulnerability
                return nz[-1]
            elif step_policy == 'trend_anchor':
                # Anchor to dominant color in window 24
                w24 = nz[-24:]
                rc = sum(1 for x in w24 if x == 'RED')
                return 'RED' if rc >= len(w24) - rc else 'BLACK'
                
        # Normal prediction at steps 1..3
        return predict_v16_1_baseline(hist)
    return predict_adaptive

# Custom simulator supporting step-aware predictors
def simulate_session_step_aware(outcomes, predictor_fn, cfg_fn, init_bank=7_500_000, profile='APEX_IDEAL'):
    bank = init_bank
    step = 1
    cdt = 0
    prev_bet = None
    mode = 'ZEBRA'; prev_mode = 'ZEBRA'; sde = 999; sim = 0
    seq_start = 'ZEBRA'; seq_n = None; zero_in_seq = 0
    hist = []
    
    wins = 0; losses = 0; resets = 0
    max_step = 1; max_dd = 0; peak = bank
    bets = []
    win_steps = []
    
    for out in outcomes:
        if bank < 1000: break
        cycle_cap = bank + cdt
        zero10 = sum(1 for x in hist[-10:] if x == 'ZERO')
        is_zero_shock = (profile != 'SHIELD_CONSERVATIVE') and (zero10 >= 2 or zero_in_seq >= 2)
        locked = cdt > 0 and (profile != 'SHIELD_CONSERVATIVE') and (not is_zero_shock) and cycle_cap >= 3_000_000 and seq_start == 'ZEBRA'
        eff_mode = 'ZEBRA' if locked else mode
        
        b0, mode_n = cfg_fn(profile, eff_mode, cycle_cap)
        if cdt > 0 and seq_n is not None:
            if is_zero_shock and step >= 2:
                eff_n = min(10, max(seq_n, mode_n), mode_n)
            else:
                eff_n = min(mode_n, seq_n)
        else:
            eff_n = mode_n
            
        from parity_ts_vs_python import exact_bet_1m, calc_net_win
        bet = exact_bet_1m(cdt, step, b0, eff_n, bank, prev_bet)
        bets.append(bet)
        
        # Pass step if predictor accepts it
        try:
            pred = predictor_fn(hist, current_step=step)
        except TypeError:
            pred = predictor_fn(hist)
            
        was_at_start = (cdt == 0 or step == 1)
        is_win = (out == pred and out != 'ZERO')
        
        if out == 'ZERO':
            net = -bet; cdt += bet; step += 1; zero_in_seq += 1; losses += 1
        elif out == pred:
            net = calc_net_win(bet)
            cdt = max(0, cdt - net)
            wins += 1; win_steps.append(step)
            if cdt == 0: step = 1; zero_in_seq = 0
        else:
            net = -bet; cdt += bet; step += 1; losses += 1
            
        if step > max_step: max_step = step
        
        # Terminal loss check
        is_terminal = not is_win and BankrollManagerMirror.is_terminal_sequence_loss(step - 1, seq_n, bet, 1_000_000)
        if is_terminal:
            resets += 1; cdt = 0; step = 1; zero_in_seq = 0
            
        bank += net
        if bank > peak: peak = bank
        dd = peak - bank
        if dd > max_dd: max_dd = dd
        
        hist.append(out)
        
        # Mode detection
        raw_m = PrngDetectorMirror.detect_mode(hist)
        zero10_next = sum(1 for x in hist[-10:] if x == 'ZERO')
        nm = "TRANSITION" if (zero10_next >= 3 and raw_m == "ZEBRA") else raw_m
        prev_mode = mode if nm != mode else prev_mode
        sim = 1 if nm != mode else sim + 1
        mode = nm; sde = 999
        
        if cdt == 0:
            seq_start = mode; seq_n = None; zero_in_seq = 0
        elif was_at_start:
            seq_start = eff_mode
            seq_n = cfg_fn(profile, eff_mode, cycle_cap)[1]
        else:
            next_zero10 = sum(1 for x in hist[-10:] if x == "ZERO")
            next_zero_shock = (profile != 'SHIELD_CONSERVATIVE') and (next_zero10 >= 2 or zero_in_seq >= 2)
            if next_zero_shock and step >= 2:
                next_locked = (bank + cdt >= 3_000_000) and seq_start == "ZEBRA"
                next_mode_n = cfg_fn(profile, "ZEBRA" if next_locked else mode, bank + cdt)[1]
                seq_n = min(10, max(seq_n if seq_n is not None else next_mode_n, next_mode_n))
        prev_bet = bet

    return {
        'net_profit': bank - init_bank,
        'final_bank': bank,
        'wins': wins,
        'losses': losses,
        'resets': resets,
        'max_step': max_step,
        'max_dd': max_dd,
        'avg_bet': sum(bets)/len(bets) if bets else 0,
        'avg_win_step': sum(win_steps)/len(win_steps) if win_steps else 0,
        'is_bust': bank < 1000
    }

print("\n" + "="*125)
print(" COMPARATIVE FINANCIAL BENCHMARK ACROSS ALL 49 SESSIONS (Capital = 7.5M ₽)")
print("="*125)
print(f"{'Engine Architecture':<34} {'Net Profit (₽)':>16} {'Win Sess':>10} {'WR (%)':>8} {'Avg Step':>9} {'Max Step':>9} {'Avg Bet (₽)':>12} {'Max DD (₽)':>14} {'Resets':>8}")
print("-" * 125)

policies = [
    ('v16.0 APEX-Neural (Current Baseline)', predict_v16_0),
    ('v16.1 Purified (Streak Mood + No Noise)', predict_v16_1_baseline),
    ('v16.1 + Anti-Phase Anchor (Step>=4)', make_v16_1_step_adaptive('trend_anchor')),
    ('v16.1 + Follow-Last at Step>=4', make_v16_1_step_adaptive('follow_last')),
]

for p_name, p_fn in policies:
    sess_res = []
    for s in sessions:
        r = simulate_session_step_aware(s['outcomes'], p_fn, get_cfg_v15_1_2, init_bank=7_500_000, profile='APEX_IDEAL')
        sess_res.append(r)
        
    tot_net = sum(r['net_profit'] for r in sess_res)
    win_sess = sum(1 for r in sess_res if r['net_profit'] > 0)
    all_w = sum(r['wins'] for r in sess_res)
    all_l = sum(r['losses'] for r in sess_res)
    overall_wr = (all_w / (all_w + all_l) * 100) if (all_w + all_l) else 0
    all_bets = [r['avg_bet'] for r in sess_res if r['avg_bet'] > 0]
    avg_bet = sum(all_bets) / len(all_bets) if all_bets else 0
    all_steps = [r['avg_win_step'] for r in sess_res if r['avg_win_step'] > 0]
    avg_step = sum(all_steps) / len(all_steps) if all_steps else 0
    max_step = max(r['max_step'] for r in sess_res)
    max_dd = max(r['max_dd'] for r in sess_res)
    tot_resets = sum(r['resets'] for r in sess_res)
    
    print(f"{p_name:<34} {tot_net:>+16,.0f} {win_sess:>6}/{len(sessions):<3} {overall_wr:>7.2f}% {avg_step:>9.2f} {max_step:>9} {avg_bet:>12,.0f} {max_dd:>14,.0f} {tot_resets:>8}")
