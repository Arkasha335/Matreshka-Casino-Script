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
        v16.0 APEX-Neural Feature Extractor: extracts 30 causal time-series features.
        Zero data leakage: strictly uses past spins up to t-1.
        """
        if not history or len(history) < 4:
            return None
        raw = [h if isinstance(h, str) else (h.get('outcome', '') if isinstance(h, dict) else getattr(h, 'outcome', '')) for h in history]
        nz = [x for x in raw if x != 'ZERO']
        if len(nz) < 3:
            return None

        feats = []

        # 1. Recent raw outcomes (last 8 non-zero spins: RED=+1, BLACK=-1)
        for k in range(1, 9):
            if len(nz) >= k:
                feats.append(1.0 if nz[-k] == 'RED' else -1.0)
            else:
                feats.append(0.0)

        # 2. Streak features
        cur_color = nz[-1]
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

        # 3. Alternation frequencies (w = 4, 6, 8, 12, 16)
        for w in [4, 6, 8, 12, 16]:
            sub = nz[-w:]
            if len(sub) >= 2:
                trans = sum(1 for i in range(1, len(sub)) if sub[i] != sub[i - 1])
                feats.append(trans / (len(sub) - 1))
            else:
                feats.append(0.5)

        # 4. Color ratios (w = 8, 16, 24)
        for w in [8, 16, 24]:
            sub = nz[-w:]
            if len(sub) > 0:
                rc = sum(1 for x in sub if x == 'RED')
                feats.append(rc / len(sub))
            else:
                feats.append(0.5)

        # 5. ZERO clustering
        z10 = sum(1 for x in raw[-10:] if x == 'ZERO')
        z25 = sum(1 for x in raw[-25:] if x == 'ZERO')
        feats.append(float(z10))
        feats.append(float(z25))

        spins_since_zero = 0
        for k in range(len(raw) - 1, -1, -1):
            if raw[k] == 'ZERO':
                break
            spins_since_zero += 1
        feats.append(float(min(spins_since_zero, 30)))

        # 6. Empirical Bayesian session transition trackers
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

        # 7. Micro-patterns (A-B-A and A-A-B)
        feats.append(1.0 if (len(nz) >= 3 and nz[-1] == nz[-3] and nz[-1] != nz[-2]) else 0.0)
        feats.append(1.0 if (len(nz) >= 3 and nz[-2] == nz[-3] and nz[-1] != nz[-2]) else 0.0)

        return feats

    @classmethod
    def forward_neural(cls, feats):
        """
        Pure forward inference pass through 24-12 MLP Neural Network.
        100.000% parity with lib/engine/prng-detector.ts.
        """
        mu = NEURAL_WEIGHTS_V16['scaler']['mean']
        scale = NEURAL_WEIGHTS_V16['scaler']['scale']
        w1 = NEURAL_WEIGHTS_V16['weights']['w1']
        b1 = NEURAL_WEIGHTS_V16['weights']['b1']
        w2 = NEURAL_WEIGHTS_V16['weights']['w2']
        b2 = NEURAL_WEIGHTS_V16['weights']['b2']
        w3 = NEURAL_WEIGHTS_V16['weights']['w3']
        b3 = NEURAL_WEIGHTS_V16['weights']['b3'][0]

        # Standardize input features
        z = [(feats[i] - mu[i]) / scale[i] for i in range(30)]

        # Layer 1: 30 -> 24, Tanh
        h1 = []
        for j in range(24):
            val = b1[j]
            for i in range(30):
                val += z[i] * w1[i][j]
            h1.append(math.tanh(val))

        # Layer 2: 24 -> 12, Tanh
        h2 = []
        for k in range(12):
            val = b2[k]
            for j in range(24):
                val += h1[j] * w2[j][k]
            h2.append(math.tanh(val))

        # Output layer: 12 -> 1, Sigmoid
        out_val = b3
        for k in range(12):
            out_val += h2[k] * w3[k][0]

        p_red = 1.0 / (1.0 + math.exp(-out_val))
        return round(p_red * 1_000_000) / 1_000_000

    @classmethod
    def get_recommendation_and_confidence(cls, history):
        """
        v16.0 APEX-Neural Predictor (Deep Neural Network + Bayesian Gated Fallback)
        100.000% parity with lib/engine/prng-detector.ts.
        """
        if not history:
            return 'RED', 50, 'АНАЛИЗ'

        raw = [h if isinstance(h, str) else (h.get('outcome', '') if isinstance(h, dict) else getattr(h, 'outcome', '')) for h in history]
        non_zero = [x for x in raw if x != 'ZERO']
        if len(non_zero) < 3:
            rec = non_zero[-1] if non_zero else 'RED'
            return rec, 50, 'АНАЛИЗ'

        # --- v16.0 APEX-Neural Evaluation ---
        feats = cls.extract_features(history)
        if feats is not None:
            p_red = cls.forward_neural(feats)
            theta = NEURAL_WEIGHTS_V16.get('theta', 0.06)
            if abs(p_red - 0.5) >= theta:
                if p_red >= 0.5:
                    conf = max(50, min(85, int(round(p_red * 100))))
                    return 'RED', conf, 'НЕЙРОСЕТЬ APEX-16'
                else:
                    conf = max(50, min(85, int(round((1.0 - p_red) * 100))))
                    return 'BLACK', conf, 'НЕЙРОСЕТЬ APEX-16'

        # --- Fallback: v15.2 Synthesized Optimal Predictor ---
        streak = cls.calc_current_streak(non_zero)
        color = non_zero[-1]
        opp_color = 'BLACK' if color == 'RED' else 'RED'

        # 1. Scan non_zero to compute running max streak
        max_streak = 1
        cur_streak = 1
        for i in range(1, len(non_zero)):
            if non_zero[i] == non_zero[i - 1]:
                cur_streak += 1
                if cur_streak > max_streak:
                    max_streak = cur_streak
            else:
                cur_streak = 1

        # 2. Count empirical transitions
        pair_cont = 1
        pair_break = 1
        s3_cont = 1
        s3_break = 1
        alt_same = 1
        alt_diff = 1

        for i in range(2, len(non_zero)):
            ps = 1
            pc = non_zero[i - 1]
            for j in range(i - 2, -1, -1):
                if non_zero[j] == pc:
                    ps += 1
                else:
                    break

            actual = non_zero[i]
            if ps == 2 and (i < 3 or non_zero[i - 3] != pc):
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
                if actual == non_zero[i - 1]:
                    alt_same += 1
                else:
                    alt_diff += 1

        # 3. Deep streak fading (streak >= 3)
        if streak >= 3:
            s3_break_rate = s3_break / (s3_cont + s3_break)
            if streak < max_streak * 0.7 and s3_break_rate < 0.50:
                return color, 52, 'СЕРИЯ (ИМПУЛЬС)'
            conf = max(50, min(75, int(round(50 + max(0, s3_break_rate - 0.48) * 60))))
            return opp_color, conf, 'ОТСКОК ОТ ПОТОЛКА'

        # 4. Pairs (streak == 2)
        if streak == 2:
            pair_cont_rate = pair_cont / (pair_cont + pair_break)
            if pair_cont_rate > 0.52:
                conf = max(50, min(65, int(round(50 + (pair_cont_rate - 0.5) * 40))))
                return color, conf, 'ПАРА (ПРОДОЛЖЕНИЕ)'
            elif pair_cont_rate < 0.48:
                conf = max(50, min(65, int(round(50 + (0.5 - pair_cont_rate) * 40))))
                return opp_color, conf, 'ПАРА (СЛОМ)'
            return color, 51, 'ПАРА (СТРАХОВКА)'

        # 5. Alternation (streak == 1)
        alt_diff_rate = alt_diff / (alt_same + alt_diff)
        w8 = non_zero[-8:]
        alt8 = cls.calc_alternation(w8)

        if alt8 >= 0.7:
            return opp_color, 55, 'ЧЕРЕДОВАНИЕ (СЛОМ)'
        elif alt8 <= 0.3:
            return color, 54, 'ЧЕРЕДОВАНИЕ (ИМПУЛЬС)'
        else:
            if alt_diff_rate > 0.52:
                return opp_color, 52, 'ЧЕРЕДОВАНИЕ (СЛОМ-АДАПТИВ)'
            elif alt_diff_rate < 0.48:
                return color, 52, 'ЧЕРЕДОВАНИЕ (ПРОДОЛЖЕНИЕ-АДАПТИВ)'
            return opp_color, 51, 'ЧЕРЕДОВАНИЕ (БАЛАНС)'


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
            return min(terminal_cap, bankroll)

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
