import sys
sys.path.insert(0, 'tools/audit')
from test_cas2_deep_study import load_clean, get_matrix
from engine_mirror import PrngDetectorMirror

sessions = load_clean()

stats = {
    'alpha_pair': {'cont': 0, 'break': 0},
    'omega_pair': {'cont': 0, 'break': 0},
    'neutral_pair': {'cont': 0, 'break': 0},
    'zebra_mode_pair': {'cont': 0, 'break': 0},
    'danger_mode_pair': {'cont': 0, 'break': 0},
    'transition_mode_pair': {'cont': 0, 'break': 0},
    'high_alt_pair': {'cont': 0, 'break': 0}, # fast_alt >= 0.65
    'low_alt_pair': {'cont': 0, 'break': 0},  # fast_alt < 0.45
    'alpha_saturated': {'cont': 0, 'break': 0}, # dom >= 0.70
    'alpha_moderate': {'cont': 0, 'break': 0},  # dom 0.55 - 0.70
    'exp_streak_low': {'cont': 0, 'break': 0},  # avgStreak <= 1.5
    'exp_streak_high': {'cont': 0, 'break': 0}, # avgStreak >= 2.2
}

for s_name, outs in sessions:
    hist = []
    for o in outs:
        if o == 'ZERO':
            hist.append(o)
            continue
        nz = [h for h in hist if h != 'ZERO']
        if len(nz) >= 2 and nz[-1] == nz[-2] and (len(nz) < 3 or nz[-3] != nz[-1]):
            # Exact cas == 2
            m = get_matrix(hist, window=15)
            alpha = m['alpha']
            omega = m['omega']
            dom = m['alphaDominance']
            cas_col = nz[-1]
            fast_alt = PrngDetectorMirror.calc_alternation(nz[-6:]) if len(nz) >= 6 else 0.5
            mode = PrngDetectorMirror.detect_mode(hist)
            exp_col = m['avgStreakRed'] if cas_col == 'RED' else m['avgStreakBlack']
            
            is_cont = (o == cas_col)
            is_break = (o in ('RED', 'BLACK') and o != cas_col)
            
            outcome_key = 'cont' if is_cont else ('break' if is_break else None)
            if outcome_key:
                if cas_col == alpha:
                    stats['alpha_pair'][outcome_key] += 1
                    if dom >= 0.70:
                        stats['alpha_saturated'][outcome_key] += 1
                    else:
                        stats['alpha_moderate'][outcome_key] += 1
                elif cas_col == omega:
                    stats['omega_pair'][outcome_key] += 1
                else:
                    stats['neutral_pair'][outcome_key] += 1
                
                if mode == 'ZEBRA':
                    stats['zebra_mode_pair'][outcome_key] += 1
                elif mode == 'DANGER':
                    stats['danger_mode_pair'][outcome_key] += 1
                else:
                    stats['transition_mode_pair'][outcome_key] += 1
                    
                if fast_alt >= 0.65:
                    stats['high_alt_pair'][outcome_key] += 1
                elif fast_alt < 0.45:
                    stats['low_alt_pair'][outcome_key] += 1
                    
                if exp_col <= 1.5:
                    stats['exp_streak_low'][outcome_key] += 1
                elif exp_col >= 2.2:
                    stats['exp_streak_high'][outcome_key] += 1

        hist.append(o)

print('=== CONDITIONAL BEHAVIOR AT cas == 2 ACROSS 2,766 SPINS ===')
for k, v in stats.items():
    tot = v['cont'] + v['break']
    if tot > 0:
        print(f"{k:<24} | Total: {tot:3d} | Cont to 3: {v['cont']:3d} ({v['cont']/tot:5.1%}) | Break to other: {v['break']:3d} ({v['break']/tot:5.1%})")
