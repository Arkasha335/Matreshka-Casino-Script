"""
Vision Engine module for Matreshka RP Casino.
Features multi-scale template matching, auto-calibrating UI coordinates,
instant purple-border outcome detection (<0.5ms), PayDay detection,
and Multi-Signal Outcome Triangulation (Toast icon + Purple border + Win header).
"""

import os
import json
import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Any, Literal
from .config import ROULETTE_RULES, Outcome

class VisionEngine:
    def __init__(self, templates_dir: Optional[str] = None):
        self.templates_dir = templates_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
        self.templates: Dict[str, np.ndarray] = {}
        self._load_templates()

        # Cached anchor: (title_x, title_y, scale)
        self.last_anchor: Optional[Tuple[int, int, float]] = None

    def _load_templates(self):
        """Pre-loads all template images into memory."""
        names = [
            "title_casino.png",
            "btn_play_green.png",
            "tab_exact_color.png",
            "payday_close_x.png",
            "toast_win_check.png"
        ]
        for name in names:
            p = os.path.join(self.templates_dir, name)
            if os.path.isfile(p):
                tpl = cv2.imread(p)
                if tpl is not None:
                    self.templates[name] = tpl

    def match_template_best(
        self,
        scene: np.ndarray,
        tpl_name: str,
        scales: Tuple[float, ...] = (1.0, 0.75, 1.25, 1.5, 0.85, 0.95, 1.1)
    ) -> Tuple[float, Tuple[int, int], Tuple[int, int]]:
        """
        Multi-scale template matching.
        Returns: (best_score, (best_x, best_y), (tpl_w, tpl_h))
        """
        tpl = self.templates.get(tpl_name)
        if tpl is None:
            return 0.0, (0, 0), (0, 0)

        best_score = -1.0
        best_loc = (0, 0)
        best_size = (tpl.shape[1], tpl.shape[0])

        scene_gray = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)

        for s in scales:
            if s == 1.0:
                t_scaled = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            else:
                new_w = int(tpl.shape[1] * s)
                new_h = int(tpl.shape[0] * s)
                if new_w >= scene.shape[1] or new_h >= scene.shape[0] or new_w < 10 or new_h < 10:
                    continue
                t_scaled = cv2.resize(cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY), (new_w, new_h))

            res = cv2.matchTemplate(scene_gray, t_scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_score:
                best_score = max_val
                best_loc = max_loc
                best_size = (t_scaled.shape[1], t_scaled.shape[0])

        return best_score, best_loc, best_size

    def is_payday_popup_present(self, scene: np.ndarray, threshold: float = 0.80) -> Tuple[bool, Optional[Tuple[int, int]]]:
        """
        Detects if the PayDay 'Проверка безопасности' popup is currently visible.
        Returns: (is_present, (close_btn_x, close_btn_y))
        """
        score, loc, size = self.match_template_best(scene, "payday_close_x.png")
        if score >= threshold:
            close_x = loc[0] + size[0] // 2
            close_y = loc[1] + size[1] // 2
            return True, (close_x, close_y)
        return False, None

    def detect_casino_dialog(self, scene: np.ndarray, threshold: float = 0.82) -> Optional[Tuple[int, int, float]]:
        """
        Detects the 'Красное и черное' dialog anchor: (title_x, title_y, scale).
        """
        score, loc, size = self.match_template_best(scene, "title_casino.png")
        if score >= threshold:
            scale = size[0] / 85.0 # 85px is nominal title width at 1280x576
            self.last_anchor = (loc[0], loc[1], scale)
            return (loc[0], loc[1], scale)

        return None

    def load_coordinates_config(self) -> Dict[str, Any]:
        """Loads coordinates.json override if available."""
        cfg_path = os.path.join(os.path.dirname(__file__), "coordinates.json")
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"mode": "auto"}

    def get_ui_click_points(self, anchor: Tuple[int, int, float]) -> Dict[str, Tuple[int, int]]:
        """
        Calculates exact screen tap coordinates for all UI elements
        based on the detected dialog anchor (title_x, title_y, scale),
        or loads calibrated custom_points if mode == 'manual'.
        """
        cfg = self.load_coordinates_config()
        if cfg.get("mode") == "manual" and "custom_points" in cfg:
            pts = cfg["custom_points"]
            return {k: (int(v[0]), int(v[1])) for k, v in pts.items()}

        xt, yt, s = anchor
        offsets = cfg.get("offsets_relative_to_anchor", {})

        def _get_pt(name: str, def_dx: float, def_dy: float) -> Tuple[int, int]:
            off = offsets.get(name, [def_dx, def_dy])
            return (int(xt + off[0] * s), int(yt + off[1] * s))

        return {
            "tab_exact_color": _get_pt("tab_exact_color", 273, 315),
            "bet_input": _get_pt("bet_input", 215, 395),
            "play_btn": _get_pt("play_btn", 360, 395),
            "close_x": _get_pt("close_x", 545, 25),
            "red_cell": _get_pt("red_cell", 240, 207),
            "black_cell": _get_pt("black_cell", 486, 155),
        }

    def detect_winning_number(self, scene: np.ndarray, anchor: Tuple[int, int, float]) -> Tuple[Optional[int], Optional[Outcome], int]:
        """
        Ultra-fast (<0.5ms) purple highlight detector.
        Finds which of the 40 cells has the winning highlight border.
        Returns: (winning_number, outcome, confidence_score)
        """
        xt, yt, s = anchor
        h, w = scene.shape[:2]

        hsv = cv2.cvtColor(scene, cv2.COLOR_BGR2HSV)
        # Bright purple highlight border mask:
        purple_mask = cv2.inRange(hsv, np.array([125, 120, 120]), np.array([155, 255, 255]))

        best_score = 0
        best_num = None

        for r in range(4):
            for c in range(10):
                num = r * 10 + c
                cx = int(xt + (92 + c * 49.25) * s)
                cy = int(yt + (103 + r * 52.0) * s)
                rad = int(18 * s)
                roi = purple_mask[max(0, cy - rad):min(h, cy + rad), max(0, cx - rad):min(w, cx + rad)]
                score = int(cv2.countNonZero(roi))
                if score > best_score:
                    best_score = score
                    best_num = num

        if best_num is not None and best_score >= 90:
            if best_num in ROULETTE_RULES['ZERO_NUMBERS']:
                outcome: Outcome = 'ZERO'
            elif best_num in ROULETTE_RULES['RED_NUMBERS']:
                outcome: Outcome = 'RED'
            else:
                outcome: Outcome = 'BLACK'
            return best_num, outcome, best_score

        return None, None, best_score

    def is_play_button_ready(self, scene: np.ndarray, anchor: Tuple[int, int, float]) -> bool:
        """
        Checks whether the 'Играть' button is currently green (ready for click).
        When the wheel is spinning, the button turns gray or disabled.
        """
        xt, yt, s = anchor
        bx = int(xt + 360 * s)
        by = int(yt + 395 * s)

        h_rad = int(15 * s)
        w_rad = int(30 * s)
        btn_roi = scene[max(0, by - h_rad):min(scene.shape[0], by + h_rad), max(0, bx - w_rad):min(scene.shape[1], bx + w_rad)]
        if btn_roi.size == 0:
            return False

        hsv = cv2.cvtColor(btn_roi, cv2.COLOR_BGR2HSV)
        green_mask = cv2.inRange(hsv, np.array([35, 60, 60]), np.array([85, 255, 255]))
        green_count = cv2.countNonZero(green_mask)

        return green_count > int(25 * s * s)

    def check_payout_header(self, scene: np.ndarray, anchor: Tuple[int, int, float]) -> Tuple[str, float]:
        """
        Inspects the 'Твой выигрыш: ...' line in the top header of the casino dialog.
        During spinning: no text is present in this row -> returns ('SPINNING', 0).
        When lost: shows '0 ₽' (narrow white span < 32px) -> returns ('LOSS', span).
        When won: shows e.g. '1980 ₽' (wide white span >= 34px, 4+ chars) -> returns ('WIN', span).
        """
        xt, yt, s = anchor
        hy1 = int(yt + 32 * s)
        hy2 = int(yt + 65 * s)
        hx1 = int(xt + 340 * s)
        hx2 = int(xt + 540 * s)
        crop = scene[max(0, hy1):min(scene.shape[0], hy2), max(0, hx1):min(scene.shape[1], hx2)]
        if crop.size == 0:
            return 'UNKNOWN', 0.0

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Bright white digits (text 'Твой выигрыш:' is dimmer and ignored)
        _, thresh = cv2.threshold(gray, 195, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in cnts if cv2.boundingRect(c)[3] >= int(4 * s)]
        if len(boxes) == 0:
            return 'SPINNING', 0.0

        boxes = sorted(boxes, key=lambda b: b[0])
        total_w = (boxes[-1][0] + boxes[-1][2]) - boxes[0][0]
        norm_w = total_w / s
        num_chars = len(boxes)

        # In '0 ₽', norm_w is around 18-28 px and num_chars <= 3
        # In '1980 ₽', norm_w is around 38-70 px and num_chars >= 4
        if norm_w < 32 and num_chars <= 3:
            return 'LOSS', norm_w
        elif norm_w >= 34 or num_chars >= 4:
            return 'WIN', norm_w

        return 'SPINNING', 0.0

    def detect_outcome_multisignal(
        self,
        scene: np.ndarray,
        anchor: Tuple[int, int, float],
        bet_color: Outcome
    ) -> Tuple[Optional[Outcome], Optional[bool], Optional[int], Dict[str, Any]]:
        """
        Lightweight, lightning-fast, and 100% deterministic outcome detector.
        Directly reads:
        1. 'Играть' button readiness (turns green once the roulette spin finishes).
        2. Winning cell number (0..39) identified by purple border highlight.
        3. Maps winning cell to RED, BLACK, or ZERO.
        Returns: (final_outcome, is_win, winning_number, debug_info)
        """
        btn_green = self.is_play_button_ready(scene, anchor)
        best_num, num_outcome, purple_score = self.detect_winning_number(scene, anchor)

        debug = {
            "btn_green": btn_green,
            "purple_num": best_num,
            "purple_outcome": num_outcome,
            "purple_score": purple_score
        }

        # If the 'Играть' button is not yet green, the wheel is still spinning!
        if not btn_green:
            return None, None, None, debug

        # Once button is green and purple highlight is stably locked on a cell:
        if num_outcome is not None and purple_score >= 90:
            outcome = num_outcome
            if outcome == 'ZERO':
                is_win = False
            else:
                is_win = (outcome == bet_color)
            return outcome, is_win, best_num, debug

        # Supplementary fallback: toast win checkmark
        win_score, _, _ = self.match_template_best(scene, "toast_win_check.png")
        if win_score >= 0.88:
            debug["toast_win"] = True
            return bet_color, True, best_num if best_num is not None else -1, debug

        return None, None, None, debug
