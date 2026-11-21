import math
import json
import os

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), 'neural_weights_v16.json')
if not os.path.exists(WEIGHTS_PATH):
    WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'lib', 'engine', 'neural_weights_v16.json')

with open(WEIGHTS_PATH, 'r', encoding='utf-8') as f:
    NEURAL_WEIGHTS_V16 = json.load(f)


GAME_RULES = {
    'TOTAL_SLOTS': 50,
    'RED_SLOTS': 24,
    'BLACK_SLOTS': 24,
    'ZERO_SLOTS': 2,
    'MIN_BET': 1000,
    'MAX_BET': 1000000,
    'TAX_RATE': 0.02,
    'WIN_NET_RATIO': 0.98,
    'EXPECTED_ZERO_INTERVAL': 25,
}

def js_round(x: float) -> int:
    return math.floor(x + 0.5)

class PrngDetectorMirror:
    @staticmethod
    def calc_alternation(arr):
        if len(arr) < 3:
            return 0.5
        transitions = sum(1 for i in range(1, len(arr)) if arr[i] != arr[i - 1])
        return transitions / (len(arr) - 1)

    @staticmethod
    def calc_current_streak(non_zero):
        if not non_zero:
            return 0
        streak = 1
        last_color = non_zero[-1]
        for i in range(len(non_zero) - 2, -1, -1):
            if non_zero[i] == last_color:
                streak += 1
            else:
                break
        return streak

    @staticmethod
    def count_streaks_gte(non_zero, min_len):
        if not non_zero:
            return 0
        count = 0
        current_streak = 1
        last_color = non_zero[0]
        for i in range(1, len(non_zero)):
            if non_zero[i] == last_color:
                current_streak += 1
            else:
                if current_streak >= min_len:
                    count += 1
                current_streak = 1
                last_color = non_zero[i]
        if current_streak >= min_len:
            count += 1
        return count

    @staticmethod
    def get_apex_matrix(history, window=24):
        non_zero = [h for h in history if h != 'ZERO'][-window:]
        red_count = non_zero.count('RED')
        black_count = non_zero.count('BLACK')
        max_streak_red = 0
        max_streak_black = 0
        current_streak = 0
        current_color = None
        streaks_red = []
        streaks_black = []

        for h in non_zero:
            if h == current_color:
                current_streak += 1
            else:
                if current_color == 'RED':
                    streaks_red.append(current_streak)
                elif current_color == 'BLACK':
                    streaks_black.append(current_streak)
                current_color = h
                current_streak = 1
            if current_color == 'RED' and current_streak > max_streak_red:
                max_streak_red = current_streak
            if current_color == 'BLACK' and current_streak > max_streak_black:
                max_streak_black = current_streak
        if current_color == 'RED':
            streaks_red.append(current_streak)
        elif current_color == 'BLACK':
            streaks_black.append(current_streak)

        avg_streak_red = sum(streaks_red) / len(streaks_red) if streaks_red else 1.5
        avg_streak_black = sum(streaks_black) / len(streaks_black) if streaks_black else 1.5

        alpha = 'NEUTRAL'
        omega = 'NEUTRAL'
        alpha_dominance = 0.5
        if non_zero:
            r_ratio = red_count / len(non_zero)
            b_ratio = black_count / len(non_zero)
            if r_ratio > 0.55:
                alpha, omega = 'RED', 'BLACK'
                alpha_dominance = r_ratio
            elif b_ratio > 0.55:
                alpha, omega = 'BLACK', 'RED'
                alpha_dominance = b_ratio
            else:
                alpha_dominance = max(r_ratio, b_ratio)

        current_active_streak = 0
        current_active_color = None
        if non_zero:
            current_active_color = non_zero[-1]
            for i in range(len(non_zero) - 1, -1, -1):
                if non_zero[i] == current_active_color:
                    current_active_streak += 1
                else:
                    break

        return {
            'alpha': alpha,
            'omega': omega,
            'alphaDominance': alpha_dominance,
            'maxStreakRed': max_streak_red,
            'maxStreakBlack': max_streak_black,
            'avgStreakRed': avg_streak_red,
            'avgStreakBlack': avg_streak_black,
            'currentActiveColor': current_active_color,
            'currentActiveStreak': current_active_streak,
        }

    @classmethod
    def detect_mode(cls, history):
        non_zero = [h for h in history if h != 'ZERO']
        if len(non_zero) < 3:
            return 'ZEBRA'

        current_streak = cls.calc_current_streak(non_zero)
        fast_alt_rate = cls.calc_alternation(non_zero[-6:])
        slow_alt_rate = cls.calc_alternation(non_zero[-15:])
        streak3plus_count = cls.count_streaks_gte(non_zero[-15:], 3)
        zero_count = history[-10:].count('ZERO')

        score = 0
        if current_streak >= 7: score -= 8
        elif current_streak == 6: score -= 6
        elif current_streak == 5: score -= 4
        elif current_streak == 4: score -= 1
        elif current_streak == 3: score += 0
        elif current_streak <= 2: score += 2

        if fast_alt_rate >= 0.80: score += 3
        elif fast_alt_rate >= 0.60: score += 1
        elif fast_alt_rate < 0.30: score -= 2

        if slow_alt_rate >= 0.70: score += 1
        elif slow_alt_rate < 0.40: score -= 1

        if streak3plus_count >= 3: score -= 2
        elif streak3plus_count == 2: score -= 1
        elif streak3plus_count == 0: score += 1

        if zero_count >= 3: score -= 3
        elif zero_count == 2: score -= 1

        if score >= 2: return 'ZEBRA'
        if score <= -2: return 'DANGER'
        return 'TRANSITION'

    @classmethod
    def detect_mode_with_hysteresis(cls, history, prev_mode, curr_mode, spins_since_danger_exit, spins_in_current_mode):
        raw_mode = cls.detect_mode(history)
        zero_count10 = history[-10:].count('ZERO')
        effective_raw_mode = 'TRANSITION' if (zero_count10 >= 3 and raw_mode == 'ZEBRA') else raw_mode
        new_mode = effective_raw_mode

        new_spins_since_danger_exit = spins_since_danger_exit + 1
        new_spins_in_current_mode = spins_in_current_mode + 1
        new_prev_mode = prev_mode

        # Rule 1: DANGER minimum hold (3 spins)
        if curr_mode == 'DANGER' and spins_in_current_mode < 3:
            new_mode = 'DANGER'

        # Rule 2: Post-DANGER cooldown (5 spins in TRANSITION)
        if curr_mode == 'DANGER' and new_mode != 'DANGER' and spins_in_current_mode >= 3:
            new_mode = 'TRANSITION'
            new_spins_since_danger_exit = 0
        elif new_spins_since_danger_exit < 5 and new_mode == 'ZEBRA':
            new_mode = 'TRANSITION'

        if new_mode != curr_mode:
            new_prev_mode = curr_mode
            new_spins_in_current_mode = 1

        return new_mode, new_prev_mode, new_spins_since_danger_exit, new_spins_in_current_mode

    @staticmethod
    def get_zebra_momentum(history):
        non_zero = [h for h in history if h != 'ZERO'][-6:]
        if len(non_zero) < 4:
            return {'followL1': True, 'confidence': 55}
        alternations = sum(1 for i in range(1, len(non_zero)) if non_zero[i] != non_zero[i - 1])
        alt_rate = alternations / (len(non_zero) - 1)
        if alt_rate >= 0.80:
            return {'followL1': False, 'confidence': 65}
        elif alt_rate >= 0.60:
            return {'followL1': True, 'confidence': 55}
        else:
            return {'followL1': True, 'confidence': 58}

    @classmethod
    def extract_features(cls, history):
        """
        v16.1 APEX-Neural Feature Extractor: extracts 30 causal time-series features.
        Zero data leakage: strictly uses past spins up to t-1.
        Features:
        1-3: Micro-memory (lags 1, 2, 3)
        4-9: Current streak dynamics (signed, abs, s=1, s=2, s=3, s>=4)
        10-13: Previous opposite streak memory (prev_s, prev_s=1, prev_s=2, prev_s>=3)
        14-17: Rolling streak mood & saturation ratio (avg_r, avg_b, diff, s/avg_cur)
        18-22: Multi-scale alternation rates (w=4, 6, 8, 12, 16)
        23-25: Color dominance ratios (w=8, 16, 24)
        26-28: Empirical Bayesian transition trackers (pair_cont, s3_break, alt_diff)
        29-30: Micro-patterns (A-B-A, A-A-B)
        """
        if not history or len(history) < 4:
            return None
        raw = [h if isinstance(h, str) else (h.get('outcome', '') if isinstance(h, dict) else getattr(h, 'outcome', '')) for h in history]
        nz = [x for x in raw if x != 'ZERO']
        if len(nz) < 3:
            return None

        feats = []

        # 1. Micro-memory: Lags 1, 2, 3 (3 features)
        for k in range(1, 4):
            if len(nz) >= k:
                feats.append(1.0 if nz[-k] == 'RED' else -1.0)
            else:
                feats.append(0.0)

        # 2. Current streak features (6 features)
        cur_color = nz[-1]
        opp_color = 'BLACK' if cur_color == 'RED' else 'RED'
        streak = 1
        for k in range(len(nz) - 2, -1, -1):
            if nz[k] == cur_color:
                streak += 1
            else:
                break
        signed_streak = streak if cur_color == 'RED' else -streak
        feats.append(float(signed_streak))
        feats.append(float(streak))
        feats.append(1.0 if streak == 1 else 0.0)
        feats.append(1.0 if streak == 2 else 0.0)
        feats.append(1.0 if streak == 3 else 0.0)
        feats.append(1.0 if streak >= 4 else 0.0)

        # 3. Previous streak features (4 features)
        prev_streak = 1
        idx_prev = len(nz) - 1 - streak
        if idx_prev >= 0:
            for k in range(idx_prev - 1, -1, -1):
                if nz[k] == opp_color:
                    prev_streak += 1
                else:
                    break
        feats.append(float(min(prev_streak, 6)))
        feats.append(1.0 if prev_streak == 1 else 0.0)
        feats.append(1.0 if prev_streak == 2 else 0.0)
        feats.append(1.0 if prev_streak >= 3 else 0.0)

        # 4. Rolling average streak per color & saturation ratio (Window 24) (4 features)
        w24 = nz[-24:]
        st_r, st_b = [], []
        if w24:
            tc = w24[0]
            tl = 1
            for j in range(1, len(w24)):
                if w24[j] == tc:
                    tl += 1
                else:
                    if tc == 'RED': st_r.append(tl)
                    else: st_b.append(tl)
                    tc = w24[j]
                    tl = 1
            if tc == 'RED': st_r.append(tl)
            else: st_b.append(tl)
        avg_r = sum(st_r) / len(st_r) if st_r else 1.8
        avg_b = sum(st_b) / len(st_b) if st_b else 1.8
        feats.append(avg_r)
        feats.append(avg_b)
        feats.append(avg_r - avg_b)

        avg_cur = avg_r if cur_color == 'RED' else avg_b
        sat_ratio = streak / max(1.0, avg_cur)
        feats.append(sat_ratio)

        # 5. Multi-scale alternation rates (w = 4, 6, 8, 12, 16) (5 features)
        for w in [4, 6, 8, 12, 16]:
            sub = nz[-w:]
            if len(sub) >= 2:
                trans = sum(1 for i in range(1, len(sub)) if sub[i] != sub[i - 1])
                feats.append(trans / (len(sub) - 1))
            else:
                feats.append(0.5)

        # 6. Color ratios (w = 8, 16, 24) (3 features)
        for w in [8, 16, 24]:
            sub = nz[-w:]
            if len(sub) > 0:
                rc = sum(1 for x in sub if x == 'RED')
                feats.append(rc / len(sub))
            else:
                feats.append(0.5)

        # 7. Empirical Bayesian session transition trackers (3 features)
        pair_cont = 1
        pair_break = 1
        s3_cont = 1
        s3_break = 1
        alt_same = 1
        alt_diff = 1

        for i in range(2, len(nz)):
            ps = 1
            pc = nz[i - 1]
            for j in range(i - 2, -1, -1):
                if nz[j] == pc:
                    ps += 1
                else:
                    break
            actual = nz[i]
            if ps == 2 and (i < 3 or nz[i - 3] != pc):
                if actual == pc:
                    pair_cont += 1
                else:
                    pair_break += 1
            elif ps >= 3:
                if actual == pc:
                    s3_cont += 1
                else:
                    s3_break += 1
            elif ps == 1:
                if actual == nz[i - 1]:
                    alt_same += 1
                else:
                    alt_diff += 1

        feats.append(pair_cont / (pair_cont + pair_break))
        feats.append(s3_break / (s3_cont + s3_break))
        feats.append(alt_diff / (alt_same + alt_diff))

        # 8. Micro-patterns (A-B-A and A-A-B) (2 features)
        feats.append(1.0 if (len(nz) >= 3 and nz[-1] == nz[-3] and nz[-1] != nz[-2]) else 0.0)
        feats.append(1.0 if (len(nz) >= 3 and nz[-2] == nz[-3] and nz[-1] != nz[-2]) else 0.0)

        return feats

    @classmethod
    def forward_neural(cls, feats):
        """
        Pure forward inference pass through Ridge-Regularized 30-feature Linear Model.
        100.000% parity with lib/engine/prng-detector.ts.
        """
        mu = NEURAL_WEIGHTS_V16['scaler']['mean']
        scale = NEURAL_WEIGHTS_V16['scaler']['scale']
        w = NEURAL_WEIGHTS_V16['weights']['w']
        b = NEURAL_WEIGHTS_V16['weights']['b']

        z = b
        for i in range(30):
            z += ((feats[i] - mu[i]) / scale[i]) * w[i]

        p_red = 1.0 / (1.0 + math.exp(-z))
        return round(p_red * 1_000_000) / 1_000_000

    @classmethod
    def get_recommendation_and_confidence(cls, history, current_step=1):
        """
        v16.2 APEX Synthesized Engine (Bayesian Transition Matrices + Deep Step Streak Shield + Regularized Causal Head)
        100.000% parity with lib/engine/prng-detector.ts.
        """
        if not history:
            return 'RED', 50, 'АНАЛИЗ'

        raw = [h if isinstance(h, str) else (h.get('outcome', '') if isinstance(h, dict) else getattr(h, 'outcome', '')) for h in history]
        non_zero = [x for x in raw if x != 'ZERO']
        if len(non_zero) < 3:
            rec = non_zero[-1] if non_zero else 'RED'
            return rec, 50, 'АНАЛИЗ'

        cur_color = non_zero[-1]
        opp_color = 'BLACK' if cur_color == 'RED' else 'RED'

        # 1. Calculate active streak
        streak = 1
        for k in range(len(non_zero) - 2, -1, -1):
            if non_zero[k] == cur_color:
                streak += 1
            else:
                break

        # -------------------------------------------------------------------------
        # SHIELD: DEEP STEP STREAK SHIELD (Step >= 5 Anti-Wipeout Law)
        # -------------------------------------------------------------------------
        if current_step >= 5 and streak >= 2:
            return cur_color, 75, f'ЗАЩИТА СЕРИИ APEX-16.2 (Шаг {current_step})'

        # 2. Fast Alternation Rate (Window 6)
        sub6 = non_zero[-6:]
        alt6 = 0.5
        if len(sub6) >= 2:
            trans = sum(1 for i in range(1, len(sub6)) if sub6[i] != sub6[i-1])
            alt6 = trans / (len(sub6) - 1)

        # 3. Macro Dominance Skew (Window 24 - Half-Wheel APEX Horizon)
        w24 = non_zero[-24:]
        red_count24 = sum(1 for c in w24 if c == 'RED')
        red_ratio24 = red_count24 / len(w24) if w24 else 0.5
        macro_dom = 'RED' if red_ratio24 > 0.55 else ('BLACK' if red_ratio24 < 0.45 else None)

        # 4. Empirical Session Transition Trackers (Bayesian Dirichlet Prior)
        pair_cont, pair_break = 1, 1
        s3_cont, s3_break = 1, 1
        alt_same, alt_diff = 1, 1
        max_streak = 1
        cstk = 1

        for i in range(1, len(non_zero)):
            if non_zero[i] == non_zero[i - 1]:
                cstk += 1
                if cstk > max_streak:
                    max_streak = cstk
            else:
                cstk = 1

        for i in range(2, len(non_zero)):
            ps = 1
            pc = non_zero[i - 1]
            for j in range(i - 2, -1, -1):
                if non_zero[j] == pc:
                    ps += 1
                else:
                    break
            act = non_zero[i]
            if ps == 2 and (i < 3 or non_zero[i - 3] != pc):
                if act == pc:
                    pair_cont += 1
                else:
                    pair_break += 1
            elif ps >= 3:
                if act == pc:
                    s3_cont += 1
                else:
                    s3_break += 1
            elif ps == 1:
                if act == non_zero[i - 1]:
                    alt_same += 1
                else:
                    alt_diff += 1

        # 5. Regularized Causal Feature Forward Pass
        p_red = 0.5
        feats = cls.extract_features(history)
        if feats:
            p_red = cls.forward_neural(feats)

        # REGIME 1: Deep Streak (streak >= 3)
        if streak >= 3:
            s3_break_rate = s3_break / (s3_cont + s3_break)
            if streak < max_streak * 0.7 and s3_break_rate < 0.46:
                return cur_color, 55, 'СЕРИЯ (ИМПУЛЬС-16.2)'
            conf = max(50, min(80, js_round(50 + max(0, s3_break_rate - 0.48) * 60)))
            return opp_color, conf, 'ОТСКОК ОТ ПОТОЛКА (16.2)'

        # REGIME 2: Pairs (streak == 2)
        if streak == 2:
            pair_cont_rate = pair_cont / (pair_cont + pair_break)
            if pair_cont_rate > 0.51:
                conf = max(50, min(65, js_round(50 + (pair_cont_rate - 0.5) * 40)))
                return cur_color, conf, 'ПАРА (РАЗГОН ДО 3)'
            elif pair_cont_rate < 0.47:
                conf = max(50, min(65, js_round(50 + (0.5 - pair_cont_rate) * 40)))
                return opp_color, conf, 'ПАРА (СЛОМ)'
            if p_red > 0.54:
                return 'RED', js_round(p_red * 100), 'ПАРА (НЕЙРО-КАЛИБРОВКА)'
            elif p_red < 0.46:
                return 'BLACK', js_round((1.0 - p_red) * 100), 'ПАРА (НЕЙРО-КАЛИБРОВКА)'
            if macro_dom is not None:
                return macro_dom, 52, 'ПАРА (МАКРО-ВЫРАВНИВАНИЕ)'
            return cur_color, 51, 'ПАРА (СТРАХОВКА)'

        # REGIME 3: Alternation / Singles (streak == 1)
        if alt6 >= 0.65:
            return opp_color, 60, 'ЗЕБРА (ПРОДОЛЖЕНИЕ-16.2)'
        elif alt6 <= 0.30:
            return cur_color, 55, 'ТРЕНД (СТАРТ ПАРЫ-16.2)'
        else:
            alt_diff_rate = alt_diff / (alt_same + alt_diff)
            if alt_diff_rate > 0.52:
                return opp_color, 53, 'ЗЕБРА (БАЙЕС-СЛОМ)'
            elif alt_diff_rate < 0.48:
                return cur_color, 53, 'ТРЕНД (БАЙЕС-ПАРА)'
            if p_red > 0.54:
                return 'RED', js_round(p_red * 100), 'НЕЙРО-БАЛАНС'
            elif p_red < 0.46:
                return 'BLACK', js_round((1.0 - p_red) * 100), 'НЕЙРО-БАЛАНС'
            return opp_color, 51, 'ЗЕБРА (БАЛАНС)'


class BankrollManagerMirror:
    @staticmethod
    def get_calibrated_ladder_config(profile, mode, bankroll):
        cap = max(GAME_RULES['MIN_BET'] * 10, bankroll)
        if profile == 'SHIELD_CONSERVATIVE':
            target_steps = 10
            if cap >= 2500000:
                nominal_b0 = 2500 if mode == 'ZEBRA' else (1800 if mode == 'TRANSITION' else 1200)
            elif cap >= 1500000:
                nominal_b0 = 2000 if mode == 'ZEBRA' else (1400 if mode == 'TRANSITION' else 1000)
            else:
                nominal_b0 = 1400 if mode == 'ZEBRA' else (1100 if mode == 'TRANSITION' else 1000)
        elif profile == 'TURBO_HARVEST':
            if cap >= 3000000:
                if mode == 'ZEBRA': nominal_b0, target_steps = 6500, 8
                elif mode == 'TRANSITION': nominal_b0, target_steps = 4000, 9
                else: nominal_b0, target_steps = 2000, 10
            else:
                if mode == 'ZEBRA': nominal_b0, target_steps = 4500, 8
                elif mode == 'TRANSITION': nominal_b0, target_steps = 3000, 9
                else: nominal_b0, target_steps = 1500, 10
        else:  # APEX_IDEAL
            if cap >= 3500000:
                if mode == 'ZEBRA': nominal_b0, target_steps = 4500, 8
                elif mode == 'TRANSITION': nominal_b0, target_steps = 2500, 10
                else: nominal_b0, target_steps = 1400, 10
            else:
                if mode == 'ZEBRA': nominal_b0, target_steps = 4000, 8
                elif mode == 'TRANSITION': nominal_b0, target_steps = 2200, 10
                else: nominal_b0, target_steps = 1200, 10
        return nominal_b0, target_steps

    @classmethod
    def get_engine_params(cls, profile, mode, bankroll):
        eff_b = max(GAME_RULES['MIN_BET'] * 10, bankroll)
        nom_b0, target_steps = cls.get_calibrated_ladder_config(profile, mode, eff_b)
        eff_b0 = max(GAME_RULES['MIN_BET'], js_round(nom_b0 / 50.0) * 50)
        terminal_cap = max(GAME_RULES['MIN_BET'], min(GAME_RULES['MAX_BET'], math.floor(eff_b / 1.90)))
        ratio = terminal_cap / max(1, eff_b0)
        exponent = 1.0 / max(1, target_steps - 1)
        dyn_mult = max(2.025, min(2.40, math.pow(ratio, exponent)))
        return {
            'baseBet': eff_b0,
            'growthFactor': dyn_mult,
            'stepsToLimit': max(1, target_steps),
        }

    @staticmethod
    def is_terminal_sequence_loss(current_step, sequence_target_steps=None, effective_bet=None, table_limit=GAME_RULES['MAX_BET']):
        if effective_bet is not None and effective_bet >= table_limit:
            return True
        if sequence_target_steps is not None and sequence_target_steps > 0 and current_step >= sequence_target_steps:
            return True
        return False

    @staticmethod
    def calculate_bet(cdt, step, mode, params, bankroll, prev_bet=None):
        base_bet = max(GAME_RULES['MIN_BET'], params['baseBet'])
        if cdt <= 0 or step <= 1:
            return min(base_bet, max(GAME_RULES['MIN_BET'], bankroll))

        target_steps = params['stepsToLimit'] or 10
        if step > target_steps:
            return base_bet
        terminal_cap = max(GAME_RULES['MIN_BET'], min(GAME_RULES['MAX_BET'], math.floor(bankroll / 1.90)))
        remaining = max(1, target_steps - step + 1)

        if remaining == 1:
            min_tbb = math.ceil((cdt + base_bet) / GAME_RULES['WIN_NET_RATIO'])
            return max(GAME_RULES['MIN_BET'], min(terminal_cap, min_tbb, bankroll))

        if prev_bet is not None and prev_bet > 0:
            prev_b = prev_bet
        else:
            prev_b = max(base_bet, js_round(base_bet * math.pow(params['growthFactor'], max(0, step - 2))))

        ratio = terminal_cap / max(1, prev_b)
        dyn_x = max(2.025, min(2.40, math.pow(ratio, 1.0 / remaining)))
        geom_bet = js_round(prev_b * dyn_x)

        min_tbb = math.ceil((cdt + base_bet) / GAME_RULES['WIN_NET_RATIO'])
        bet = max(min_tbb, geom_bet)

        if remaining == 2 and terminal_cap >= 900000:
            safe_debt_limit = 975000 - cdt
            if safe_debt_limit > min_tbb:
                bet = min(bet, safe_debt_limit)

        final_bet = max(GAME_RULES['MIN_BET'], min(bet, GAME_RULES['MAX_BET'], bankroll))
        return js_round(final_bet)


if __name__ == '__main__':
    with open(r'd:\Downloads\matreshka_session_2026-11-10 (2).json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    meta = data['metadata']
    bank = meta['initialBankroll']
    profile = meta['strategyProfile']
    history = []
    step = 1
    cdt = 0
    curr_mode = 'ZEBRA'
    prev_mode = 'ZEBRA'
    spins_since_danger_exit = 999
    spins_in_curr_mode = 0

    mismatches = 0
    for i, log in enumerate(data['logs']):
        params = BankrollManagerMirror.get_engine_params(profile, curr_mode, bank)
        prev_bet_amt = history[-1]['bet'] if (step > 1 and history) else None
        bet = BankrollManagerMirror.calculate_bet(cdt, step, curr_mode, params, bank, prev_bet_amt)
        rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence([h['outcome'] for h in history])

        outcome = log['input_result']
        if rec != log['recommended_action'] or bet != log['current_bet'] or curr_mode != log['current_mode'] or step != log['current_step'] or state != log['server_state_detected']:
            mismatches += 1
            print(f"MISMATCH at spin {i+1}:")
            print(f"  Mirror: rec={rec}, bet={bet}, mode={curr_mode}, step={step}, state={state}")
            print(f"  Log:    rec={log['recommended_action']}, bet={log['current_bet']}, mode={log['current_mode']}, step={log['current_step']}, state={log['server_state_detected']}")

        if outcome == 'ZERO':
            is_win = False
            net = -bet
            cdt += bet
            step += 1
        elif rec == outcome:
            is_win = True
            net = js_round(bet * 0.98)
            cdt = max(0, js_round(cdt - net))
            if cdt < 10:
                cdt = 0
            if cdt == 0:
                step = 1
        else:
            is_win = False
            net = -bet
            cdt += bet
            step += 1

        bank += net
        history.append({'outcome': outcome, 'bet': bet})
        hist_outcomes = [h['outcome'] for h in history]
        curr_mode, prev_mode, spins_since_danger_exit, spins_in_curr_mode = PrngDetectorMirror.detect_mode_with_hysteresis(
            hist_outcomes, prev_mode, curr_mode, spins_since_danger_exit, spins_in_curr_mode
        )

    print(f"Parity check on matreshka_session_2026-11-10 (2).json ({len(data['logs'])} spins): Mismatches = {mismatches}, Final Bankroll Mirror={bank} vs Log={meta['currentBankroll']}")
