"""
Emulator & Android Instance Optimizer for MuMu Player 12.
Applies Android settings via ADB to maximize FPS efficiency, disable animations,
mute audio, and prevent sleep, allowing massive multi-account scaling.
"""

import sys
import os
import argparse

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from bot.adb_controller import ADBController

def optimize_instance(serial: str):
    print(f"\n[*] Начинаем оптимизацию инстанса {serial}...")
    ctrl = ADBController(serial=serial)
    if not ctrl.connect():
        print(f"[!] Ошибка подключения к {serial}. Убедитесь, что эмулятор запущен.")
        return

    commands = [
        # 1. Disable screen timeout / sleep
        ("Отключение спящего режима", ["shell", "settings", "put", "system", "screen_off_timeout", "2147483647"]),
        # 2. Disable window animations (speeds up dialog rendering & reduces GPU load)
        ("Отключение анимаций окон", ["shell", "settings", "put", "global", "window_animation_scale", "0.0"]),
        ("Отключение анимаций переходов", ["shell", "settings", "put", "global", "transition_animation_scale", "0.0"]),
        ("Отключение шкалы аниматора", ["shell", "settings", "put", "global", "animator_duration_scale", "0.0"]),
        # 3. Mute media volume to prevent audio CPU interrupts
        ("Отключение звука Android (Mute)", ["shell", "cmd", "audio", "set-volume", "3", "0"]),
        # 4. Lock orientation
        ("Блокировка акселерометра", ["shell", "settings", "put", "system", "accelerometer_rotation", "0"]),
    ]

    for desc, cmd in commands:
        res = ctrl._run_cmd(cmd)
        status = "OK" if res.returncode == 0 else "FAIL"
        print(f"    - {desc:<35} [{status}]")

    print(f"\n[+] Инстанс {serial} успешно оптимизирован!")
    print("\n[РЕКОМЕНДАЦИИ ПО НАСТРОЙКЕ MUMU MULTI-DRIVE ДЛЯ ФЕРМЫ]:")
    print(" 1. Лимит FPS: Выставьте 15–20 FPS в настройках каждого окна (снизит нагрузку на видеокарту на 75%).")
    print(" 2. Разрешение: Выставьте 1280x720 (DPI 160) или 960x540 (DPI 120).")
    print(" 3. Выделение памяти: 1 vCPU и 1536–2048 MB RAM на одно окно.")
    print(" 4. Рендеринг: Выберите DirectX (Speed+) в настройках графики MuMu.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize MuMu Player instance for bot farming")
    parser.add_argument("--port", type=str, default="127.0.0.1:16384", help="ADB Serial or Port (default: 127.0.0.1:16384)")
    args = parser.parse_args()

    serial = args.port
    if not ":" in serial:
        serial = f"127.0.0.1:{serial}"
    optimize_instance(serial)
