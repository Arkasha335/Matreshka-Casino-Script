import math
import json

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
    def get_apex_matrix(history, window=15):
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
    def get_recommendation_and_confidence(cls, history):
        if not history:
            return 'RED', 50, 'АНАЛИЗ'

        matrix = cls.get_apex_matrix(history)
        non_zero = [h for h in history if h != 'ZERO']

        recommendation = 'RED'
        confidence = 50
        state = 'АНАЛИЗ'

        # MPD
        if len(non_zero) >= 4:
            L1, L2, L3, L4 = non_zero[-1], non_zero[-2], non_zero[-3], non_zero[-4]
            if L1 == L3 and L2 == L4 and L1 != L2:
                recommendation = 'BLACK' if L1 == 'RED' else 'RED'
                return recommendation, 82, 'ЭХО-ПАТТЕРН'
            if L1 == L2 and L2 == L3 and L4 != L1:
                recommendation = 'BLACK' if L1 == 'RED' else 'RED'
                return recommendation, 78, 'ВОЛНА (СЛОМ СЕРИИ)'

        if len(non_zero) < 2:
            recommendation = non_zero[-1] if non_zero else 'RED'
            return recommendation, confidence, state

        L1, L2 = non_zero[-1], non_zero[-2]

        if matrix['currentActiveColor'] and matrix['currentActiveStreak'] >= 3:
            recommendation = 'BLACK' if matrix['currentActiveColor'] == 'RED' else 'RED'
            confidence = min(95, 80 + (matrix['currentActiveStreak'] - 3) * 5)
            state = 'ОТСКОК ОТ ПОТОЛКА'
        elif L1 == L2:
            if L1 == matrix['alpha'] and matrix['alphaDominance'] >= 0.70:
                recommendation = 'BLACK' if L1 == 'RED' else 'RED'
                confidence = 75
                state = 'СЛОМ АЛЬФА-НАСЫЩЕНИЯ'
            else:
                recommendation = L1
                confidence = 65
                state = 'АЛЬФА-ПАРА' if L1 == matrix['alpha'] else ('ОМЕГА-ИМПУЛЬС' if L1 == matrix['omega'] else 'ПАРА (ПРОДОЛЖЕНИЕ)')
        else:
            zebra = cls.get_zebra_momentum(history)
            recommendation = L1 if zebra['followL1'] else ('BLACK' if L1 == 'RED' else 'RED')
            confidence = zebra['confidence']
            state = 'ЧЕРЕДОВАНИЕ (FOLLOW)' if zebra['followL1'] else 'ЧЕРЕДОВАНИЕ (BREAK)'

        if L1 == matrix['alpha'] and L2 == matrix['omega']:
            omega_streak_before = 0
            for i in range(len(non_zero) - 2, -1, -1):
                if non_zero[i] == matrix['omega']:
                    omega_streak_before += 1
                else:
                    break
            if omega_streak_before >= 2:
                recommendation = matrix['alpha']
                confidence = 85
                state = 'ЗАРОЖДЕНИЕ АЛЬФЫ'

        return recommendation, confidence, state


class BankrollManagerMirror:
    @staticmethod
    def get_calibrated_ladder_config(profile, mode, bankroll):
        b = max(GAME_RULES['MIN_BET'] * 10, bankroll)
        if profile == 'TURBO_HARVEST':
            if b >= 3000000:
                if mode == 'ZEBRA': return 3500, 9
                if mode == 'TRANSITION': return 1800, 10
                return 1000, 10
            elif b >= 1800000:
                if mode == 'ZEBRA': return 2500, 9
                if mode == 'TRANSITION': return 1500, 10
                return 1000, 10
            else:
                if mode == 'ZEBRA': return 1500, 10
                return 1000, 10
        elif profile == 'SHIELD_CONSERVATIVE':
            if b >= 3000000:
                if mode == 'ZEBRA': return 2000, 10
                if mode == 'TRANSITION': return 1200, 10
                return 1000, 10
            elif b >= 1800000:
                if mode == 'ZEBRA': return 1500, 10
                if mode == 'TRANSITION': return 1000, 10
                return 1000, 10
            else:
                return 1000, 10
        else:  # APEX_IDEAL
            if b >= 3000000:
                if mode == 'ZEBRA': return 3000, 9
                if mode == 'TRANSITION': return 1500, 10
                return 1000, 10
            elif b >= 1800000:
                if mode == 'ZEBRA': return 2000, 9
                if mode == 'TRANSITION': return 1200, 10
                return 1000, 10
            elif b >= 1000000:
                if mode == 'ZEBRA': return 1500, 10
                if mode == 'TRANSITION': return 1000, 10
                return 1000, 10
            else:
                return 1000, 10

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
    def calculate_bet(cdt, step, mode, params, bankroll, prev_bet=None):
        base_bet = max(GAME_RULES['MIN_BET'], params['baseBet'])
        if cdt <= 0 or step <= 1:
            return min(base_bet, max(GAME_RULES['MIN_BET'], bankroll))

        target_steps = params['stepsToLimit'] or 10
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
