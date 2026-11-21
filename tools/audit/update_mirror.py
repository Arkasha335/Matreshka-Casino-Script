import os

p = 'tools/audit/engine_mirror.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()

# Locate start of get_recommendation_and_confidence and end of it (class BankrollManagerMirror)
start_tag = "    @classmethod\n    def get_recommendation_and_confidence(cls, history):"
end_tag = "class BankrollManagerMirror:"

start_idx = content.find(start_tag)
end_idx = content.find(end_tag)

if start_idx == -1 or end_idx == -1:
    print(f"Error finding tags: start={start_idx}, end={end_idx}")
    exit(1)

new_func = """    @classmethod
    def get_recommendation_and_confidence(cls, history, current_step=1):
        \"\"\"
        v16.2 APEX Synthesized Engine (Bayesian Transition Matrices + Deep Step Streak Shield + Regularized Causal Head)
        100.000% parity with lib/engine/prng-detector.ts.
        \"\"\"
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
            conf = max(50, min(80, int(round(50 + max(0, s3_break_rate - 0.48) * 60))))
            return opp_color, conf, 'ОТСКОК ОТ ПОТОЛКА (16.2)'

        # REGIME 2: Pairs (streak == 2)
        if streak == 2:
            pair_cont_rate = pair_cont / (pair_cont + pair_break)
            if pair_cont_rate > 0.51:
                conf = max(50, min(65, int(round(50 + (pair_cont_rate - 0.5) * 40))))
                return cur_color, conf, 'ПАРА (РАЗГОН ДО 3)'
            elif pair_cont_rate < 0.47:
                conf = max(50, min(65, int(round(50 + (0.5 - pair_cont_rate) * 40))))
                return opp_color, conf, 'ПАРА (СЛОМ)'
            if p_red > 0.54:
                return 'RED', int(round(p_red * 100)), 'ПАРА (НЕЙРО-КАЛИБРОВКА)'
            elif p_red < 0.46:
                return 'BLACK', int(round((1.0 - p_red) * 100)), 'ПАРА (НЕЙРО-КАЛИБРОВКА)'
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
                return 'RED', int(round(p_red * 100)), 'НЕЙРО-БАЛАНС'
            elif p_red < 0.46:
                return 'BLACK', int(round((1.0 - p_red) * 100)), 'НЕЙРО-БАЛАНС'
            return opp_color, 51, 'ЗЕБРА (БАЛАНС)'\n\n\n"""

updated = content[:start_idx] + new_func + content[end_idx:]

with open(p, 'w', encoding='utf-8') as f:
    f.write(updated)

print(f"Successfully updated {p}!")
