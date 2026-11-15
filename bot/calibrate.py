"""
Interactive Calibration & Test Utility for Matreshka RP Casino.
Allows visual coordinate verification, single-step tap testing,
manual coordinate overrides, and full 1-spin verification.
"""

import os
import sys
import json
import time
import cv2
import numpy as np

# Ensure parent directory is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bot.adb_controller import ADBController
from bot.vision_engine import VisionEngine
from bot.config import BotConfig

COORDS_FILE = os.path.join(CURRENT_DIR, "coordinates.json")
ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity\brain\32c77e7d-50c9-423e-9f18-f34ef4c773ae"


def load_coords_cfg():
    if os.path.isfile(COORDS_FILE):
        try:
            with open(COORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"mode": "auto", "custom_points": {}}


def save_coords_cfg(data):
    with open(COORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[*] Конфигурация координат успешно сохранена в: {COORDS_FILE}")


class CasinoCalibrator:
    def __init__(self, serial=None):
        self.adb = ADBController(serial=serial)
        self.adb.connect()
        self.vision = VisionEngine(os.path.join(CURRENT_DIR, "templates"))

    def capture_and_annotate(self):
        print("\n[*] Захват экрана с эмулятора...")
        scene = self.adb.screencap()
        if scene is None:
            print("[ОШИБКА] Не удалось получить скриншот через ADB. Проверьте подключение эмулятора.")
            return None, None

        h, w = scene.shape[:2]
        print(f"[*] Разрешение экрана устройства: {w}x{h}")

        anchor = self.vision.detect_casino_dialog(scene)
        if not anchor:
            print("[ВНИМАНИЕ] Диалог 'Красное и черное' не обнаружен на экране!")
            print("Убедитесь, что персонаж подошел к столу рулетки и открыл интерфейс игры.")
            preview_path = os.path.join(CURRENT_DIR, "screen_debug.png")
            cv2.imwrite(preview_path, scene)
            print(f"[*] Текущий кадр сохранен для отладки: {preview_path}")
            return scene, None

        xt, yt, s = anchor
        print(f"[OK] Диалог рулетки обнаружен! Заголовок: X={xt}, Y={yt}, Масштаб={s:.2f}")

        pts = self.vision.get_ui_click_points(anchor)

        # Draw overlays
        annotated = scene.copy()
        colors = {
            "tab_exact_color": (255, 105, 180),  # Hot pink
            "red_cell": (0, 0, 255),              # Red
            "black_cell": (0, 0, 0),              # Black
            "bet_input": (0, 255, 255),           # Yellow
            "play_btn": (0, 255, 0),              # Green
            "close_x": (255, 0, 0),               # Blue
        }

        labels = {
            "tab_exact_color": "1. Tab Exact Color",
            "red_cell": "2. Red (Cell 23)",
            "black_cell": "3. Black (Cell 18)",
            "bet_input": "4. Bet Input",
            "play_btn": "5. Play Button",
            "close_x": "6. Close [X]"
        }

        print("\nТекущие координаты кликов:")
        print("-" * 55)
        for key, (px, py) in pts.items():
            lbl = labels.get(key, key)
            color = colors.get(key, (0, 255, 0))
            # Crosshair
            cv2.circle(annotated, (px, py), 12, color, 2)
            cv2.circle(annotated, (px, py), 3, (0, 255, 255), -1)
            cv2.line(annotated, (px - 18, py), (px + 18, py), color, 1)
            cv2.line(annotated, (px, py - 18), (px, py + 18), color, 1)
            cv2.putText(annotated, f"{lbl} ({px},{py})", (px + 15, py - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
            cv2.putText(annotated, f"{lbl} ({px},{py})", (px + 15, py - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            print(f" {lbl:<25} : X = {px:<5} Y = {py:<5}")
        print("-" * 55)

        preview_local = os.path.join(CURRENT_DIR, "calibration_preview.png")
        cv2.imwrite(preview_local, annotated)
        print(f"[OK] Размеченное превью сохранено в: {preview_local}")

        if os.path.isdir(ARTIFACTS_DIR):
            art_path = os.path.join(ARTIFACTS_DIR, "calibration_preview.png")
            cv2.imwrite(art_path, annotated)

        return annotated, pts

    def test_single_tap(self, point_name, pts):
        if not pts or point_name not in pts:
            print(f"[ОШИБКА] Координата '{point_name}' не определена.")
            return

        x, y = pts[point_name]
        print(f"\n[*] Выполняю тестовый клик по '{point_name}' в точку ({x}, {y})...")
        self.adb.tap(x, y, jitter=0)
        print("[OK] Клик отправлен. Посмотрите на экран эмулятора!")

    def test_bet_input(self, pts, amount=1000):
        if not pts or "bet_input" not in pts:
            print("[ОШИБКА] Поле bet_input не определено.")
            return

        x, y = pts["bet_input"]
        print(f"\n[*] Тестирование ввода суммы: клик по ({x}, {y}) -> очистка -> ввод '{amount}' -> Enter (keycode 66)...")
        self.adb.clear_and_type(x, y, str(amount), backspaces=8, post_delay=0.1, press_enter=True)
        print("[OK] Сумма введена и подтверждена клавишей Enter! Проверьте, загорелась ли кнопка 'Играть' зеленым.")

    def test_full_spin(self, pts, amount=1000, color='RED'):
        print(f"\n==========================================")
        print(f" ТЕСТОВЫЙ ПОЛНЫЙ СПИН: {amount} ₽ на {color}")
        print(f"==========================================")
        if not pts:
            print("[ОШИБКА] Сначала сделайте разметку стола!")
            return

        # 1. Tab
        print("[1/5] Переключение на вкладку 'Точный цвет'...")
        tab_x, tab_y = pts["tab_exact_color"]
        self.adb.tap(tab_x, tab_y, jitter=1)
        time.sleep(0.05)

        # 2. Cell
        target_cell = pts["red_cell"] if color == 'RED' else pts["black_cell"]
        print(f"[2/5] Выбор ячейки ({color}) в ({target_cell[0]}, {target_cell[1]})...")
        self.adb.tap(target_cell[0], target_cell[1], jitter=1)
        time.sleep(0.05)

        # 3. Amount + Enter
        bet_x, bet_y = pts["bet_input"]
        print(f"[3/5] Ввод ставки {amount} ₽ и отправка Enter...")
        self.adb.clear_and_type(bet_x, bet_y, str(amount), backspaces=8, post_delay=0.06, press_enter=True)
        time.sleep(0.08)

        # 4. Play
        play_x, play_y = pts["play_btn"]
        print(f"[4/5] Нажатие кнопки 'Играть' в ({play_x}, {play_y})...")
        self.adb.tap(play_x, play_y, jitter=1)
        start_t = time.time()

        # 5. Dynamic scan
        print("[5/5] Вращение рулетки (~6 сек)...")
        time.sleep(4.8)  # Physical wheel rotation sleep

        detected = False
        while time.time() - start_t < 25.0:
            elapsed = time.time() - start_t
            scene = self.adb.screencap()
            if scene is None:
                time.sleep(0.12)
                continue

            anchor = self.vision.detect_casino_dialog(scene)
            if not anchor:
                time.sleep(0.12)
                continue

            outcome, is_win, num, debug = self.vision.detect_outcome_multisignal(scene, anchor, color)
            if elapsed >= 5.0 and outcome is not None and is_win is not None:
                res_str = "ВЫИГРЫШ" if is_win else "ПРОИГРЫШ"
                print(f"\n[OK] Раунд завершен за {elapsed:.2f} сек!")
                print(f" [ИТОГ] Выпало число: #{num} | Цвет: {outcome} | Результат: {res_str}")
                print(f" [Детали]: {debug}")
                detected = True
                break

            print(f" Ожидание остановки шарика и фиксации выплаты... ({elapsed:.1f}с)", end="\r")
            time.sleep(0.12)

        if not detected:
            print("\n[!] Таймаут ожидания исхода (более 25с).")


def run_interactive_menu():
    cal = CasinoCalibrator()
    cached_pts = None

    while True:
        cfg = load_coords_cfg()
        current_mode = cfg.get("mode", "auto")

        print("\n" + "=" * 55)
        print(f"   ИНТЕРАКТИВНЫЙ КАЛИБРАТОР РУЛЕТКИ MT CASINO")
        print(f"   Устройство: {cal.adb.serial} | Режим: [{current_mode.upper()}]")
        print("=" * 55)
        print(" 1. Сделать скриншот и разметить координаты (Превью)")
        print(" 2. Тестовый клик по табу 'Точный цвет'")
        print(" 3. Тестовый клик по красной ячейке")
        print(" 4. Тестовый клик по черной ячейке")
        print(" 5. Тестовый ввод ставки (1000 руб + Enter)")
        print(" 6. Тестовый клик по кнопке 'Играть'")
        print(" 7. ЗАПУСТИТЬ 1 ТЕСТОВЫЙ ПОЛНЫЙ СПИН (1000 руб)")
        print(" 8. Ручной ввод координат (Переопределить X, Y)")
        print(" 9. Переключить режим (auto / manual)")
        print(" 0. Выход в главное меню")
        print("-" * 55)

        choice = input("Выберите действие [0-9]: ").strip()

        if choice == "1":
            _, cached_pts = cal.capture_and_annotate()
        elif choice == "2":
            if not cached_pts:
                _, cached_pts = cal.capture_and_annotate()
            cal.test_single_tap("tab_exact_color", cached_pts)
        elif choice == "3":
            if not cached_pts:
                _, cached_pts = cal.capture_and_annotate()
            cal.test_single_tap("red_cell", cached_pts)
        elif choice == "4":
            if not cached_pts:
                _, cached_pts = cal.capture_and_annotate()
            cal.test_single_tap("black_cell", cached_pts)
        elif choice == "5":
            if not cached_pts:
                _, cached_pts = cal.capture_and_annotate()
            cal.test_bet_input(cached_pts, 1000)
        elif choice == "6":
            if not cached_pts:
                _, cached_pts = cal.capture_and_annotate()
            cal.test_single_tap("play_btn", cached_pts)
        elif choice == "7":
            if not cached_pts:
                _, cached_pts = cal.capture_and_annotate()
            cal.test_full_spin(cached_pts, 1000, 'RED')
        elif choice == "8":
            print("\n--- РУЧНОЙ ВВОД КООРДИНАТ ---")
            print("Введите новые координаты X и Y через пробел (или Enter чтобы оставить как есть):")
            pts = cfg.get("custom_points", {})
            for key in ["tab_exact_color", "red_cell", "black_cell", "bet_input", "play_btn", "close_x"]:
                old = pts.get(key, [0, 0])
                val = input(f" {key:<20} [текущие: {old[0]} {old[1]}]: ").strip()
                if val:
                    try:
                        px, py = map(int, val.split())
                        pts[key] = [px, py]
                    except ValueError:
                        print(" [!] Неверный формат, оставлено старое значение.")
            cfg["custom_points"] = pts
            cfg["mode"] = "manual"
            save_coords_cfg(cfg)
            print("[OK] Режим переключен на MANUAL с новыми координатами!")
        elif choice == "9":
            new_mode = "manual" if current_mode == "auto" else "auto"
            cfg["mode"] = new_mode
            save_coords_cfg(cfg)
            print(f"[OK] Режим работы переключен на: {new_mode.upper()}")
        elif choice in ("0", "b", "back", "q", "quit", "exit", "отмена", "назад"):
            break
        else:
            print("[!] Неверный ввод.")


if __name__ == "__main__":
    run_interactive_menu()
