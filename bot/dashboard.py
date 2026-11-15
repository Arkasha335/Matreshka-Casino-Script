"""
Master Interactive Terminal Dashboard & Bot Farm Manager for Matreshka RP Casino.
App-like dynamic control: live multi-instance telemetry, non-blocking agent management,
independent start/pause/resume/stop, on-the-fly instance additions, and zero UI flickering.
"""

import sys
import os
import time
import threading
import signal
import traceback
from typing import Dict, List, Optional, Any

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from bot.config import BotConfig, StrategyProfile
from bot.state_machine import CasinoBot
from bot.mumu_manager import MuMuManagerCLI

# Safe Windows keypress check
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def format_seconds(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

class ActiveBotInstance:
    """Encapsulates a single bot agent running in an independent background thread."""
    def __init__(self, vm_index: int, name: str, port: int, config: BotConfig):
        self.vm_index = vm_index
        self.name = name
        self.port = port
        self.config = config
        self.telemetry: Dict[str, Any] = {
            "device_name": name,
            "serial": config.device_serial,
            "state": "CONNECTING",
            "is_paused": False,
            "spin": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "initial_bankroll": config.initial_bankroll,
            "bankroll": config.initial_bankroll,
            "profit": 0,
            "peak_bankroll": config.initial_bankroll,
            "max_drawdown": 0,
            "step": 1,
            "cdt": 0,
            "mode": "ZEBRA",
            "last_event": "Подключение к эмулятору...",
            "stop_reason": None,
            "uptime_sec": 0,
            "error": None
        }
        self.bot = CasinoBot(
            config=config,
            on_status_update=self._on_update,
            silent=True,
            device_name=name
        )
        self.thread: Optional[threading.Thread] = None

    def _on_update(self, data: Dict[str, Any]):
        self.telemetry.update(data)

    def start(self):
        def _runner():
            try:
                self.bot.run()
            except Exception as exc:
                tb = traceback.format_exc()
                self.telemetry["state"] = "ERROR"
                self.telemetry["error"] = tb
                self.telemetry["last_event"] = f"Сбой потока: {exc}"

        self.thread = threading.Thread(target=_runner, daemon=True)
        self.thread.start()

    def pause(self):
        self.bot.pause()
        self.telemetry["is_paused"] = True
        self.telemetry["state"] = "PAUSED"

    def resume(self):
        self.bot.resume()
        self.telemetry["is_paused"] = False
        self.telemetry["state"] = "RUNNING"

    def stop(self):
        self.bot.stop()
        self.telemetry["state"] = "STOPPED"

    def is_active(self) -> bool:
        return self.bot.is_running and not self.bot.is_paused

    def is_alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

class MasterDashboard:
    """Master Application Manager for all Bot Agents."""
    def __init__(self):
        self.active_bots: Dict[int, ActiveBotInstance] = {}
        self.is_running = True
        self.start_time = time.time()
        self.last_status_msg = "Готов к работе. Выберите команду управления."

    def get_detected_devices(self) -> Dict[str, Any]:
        """Queries MuMu Player CLI for instances."""
        return MuMuManagerCLI.get_instances_info()

    def _read_key(self) -> Optional[str]:
        """Non-blocking keyboard check on Windows."""
        if not HAS_MSVCRT:
            return None
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                msvcrt.getch() # swallow multi-byte keys
                return None
            try:
                return ch.decode('utf-8', errors='ignore').lower()
            except Exception:
                return None
        return None

    def render_screen(self):
        """Renders comprehensive, structured, zero-spam management view."""
        clear_screen()
        uptime = int(time.time() - self.start_time)
        devices = self.get_detected_devices()

        total_spins = sum(b.telemetry.get("spin", 0) for b in self.active_bots.values())
        total_profit = sum(b.telemetry.get("profit", 0) for b in self.active_bots.values())
        active_count = sum(1 for b in self.active_bots.values() if b.is_active())

        profit_total_str = f"{total_profit:+,.0f} ₽"

        print("=" * 88)
        print("           МАТРЁШКА RP • ИНТЕРАКТИВНЫЙ ЦЕНТР УПРАВЛЕНИЯ БОТАМИ (v15.0 APEX)")
        print("=" * 88)
        print(f" ОБЩИЙ ДОХОД: {profit_total_str:<12} | АКТИВНО: {active_count}/{len(self.active_bots)} ботов | СПИНОВ: {total_spins} | ВРЕМЯ: {format_seconds(uptime)}")
        print("-" * 88)

        # 1. Devices Table
        print(f" {'#':<3} {'ИМЯ ЭМУЛЯТОРА':<20} {'ВЕРСИЯ':<12} {'СТАТУС MUMU':<14} {'ПОРТ':<8} {'СТАТУС АГЕНТА':<16}")
        print("-" * 88)
        if not devices:
            print(" [!] Не найдено устройств MuMu Player 12.")
        else:
            for idx_str, d_info in sorted(devices.items(), key=lambda x: int(x[0])):
                idx = int(idx_str)
                name = d_info.get("name", f"Instance {idx}")
                aver = f"Android {d_info.get('android_version', '12')}"
                is_mumu_started = d_info.get("is_android_started", False)
                mumu_status = "РАБОТАЕТ" if is_mumu_started else "ВЫКЛЮЧЕН"
                port = d_info.get("adb_port", 16384 + idx * 32)

                bot_inst = self.active_bots.get(idx)
                if bot_inst:
                    t = bot_inst.telemetry
                    state = t.get("state", "UNKNOWN")
                    if t.get("is_paused"):
                        agent_status = "ПАУЗА [P]"
                    elif state == "ERROR":
                        agent_status = "ОШИБКА (!)"
                    elif state == "STOPPED":
                        agent_status = "ОСТАНОВЛЕН"
                    else:
                        agent_status = f"В ИГРЕ (#{t.get('spin', 0)})"
                else:
                    agent_status = "НЕ НАЗНАЧЕН"

                print(f" {idx:<3} {name:<20} {aver:<12} {mumu_status:<14} {port:<8} {agent_status:<16}")

        print("-" * 88)

        # 2. Detailed Live Telemetry for Active Bots
        if not self.active_bots:
            print(" [*] Нет запущенных ботов. Нажмите [A], чтобы запустить бота на любом окне.")
        else:
            print(" ДЕТАЛЬНАЯ ТЕЛЕМЕТРИЯ АКТИВНЫХ АГЕНТОВ:")
            for idx, inst in sorted(self.active_bots.items()):
                t = inst.telemetry
                state = t.get("state", "UNKNOWN")
                spins = t.get("spin", 0)
                wins = t.get("wins", 0)
                losses = t.get("losses", 0)
                win_rate = t.get("win_rate", 0.0)
                bank = t.get("bankroll", inst.config.initial_bankroll)
                profit = t.get("profit", 0)
                peak = t.get("peak_bankroll", bank)
                max_dd = t.get("max_drawdown", 0)
                mode = t.get("mode", "ZEBRA")
                step = t.get("step", 1)
                cdt = t.get("cdt", 0)
                event = t.get("last_event", "Ожидание...")
                err = t.get("error")

                p_str = f"{profit:+,.0f} ₽"
                mode_str = f"{mode}" if not inst.config.flat_bet_mode else f"{mode} (Фикс 1000 ₽)"

                rec_state = t.get("recommendation_state", "АНАЛИЗ")
                conf = t.get("confidence", 50)
                flags = []
                if t.get("is_zero_shock"):
                    flags.append("⚡ ZERO-SHOCK")
                if t.get("is_zebra_locked"):
                    flags.append("🔒 ZEBRA-LOCK")
                flag_str = (" | " + " ".join(flags)) if flags else ""

                d_stats = t.get("detailed_stats", {})
                roi_val = d_stats.get("roi", round(profit / inst.config.initial_bankroll * 100, 2) if inst.config.initial_bankroll > 0 else 0.0)

                pause_flag = " [НА ПАУЗЕ]" if t.get("is_paused") else ""
                print(f" ┌── [БОТ #{idx}: {inst.name}] Порт: {inst.port} | Состояние: {state}{pause_flag} | Спинов: {spins}")
                print(f" │   • Баланс: {bank:,.0f} ₽ ({p_str}, ROI: {roi_val:+.2f}%) | Винрейт: {win_rate}% ({wins} В / {losses} П)")
                print(f" │   • Режим: {mode_str} | Шаг: {step} | CDT: {cdt:,.0f} ₽ | Пик: {peak:,.0f} ₽ | Просадка: {max_dd:,.0f} ₽")
                print(f" │   • Аналитика: {rec_state} (Уверенность: {conf}%){flag_str}")
                print(f" └── • Событие: {event}")
                if err:
                    print(f"     [!] ОШИБКА В ПОТОКЕ: {err.splitlines()[-1] if err.splitlines() else err}")

        print("=" * 88)
        print(f" УВЕДОМЛЕНИЕ: {self.last_status_msg}")
        print("-" * 88)
        print(" КОМАНДЫ (нажмите соответствующую клавишу):")
        print("   [A] Запустить / Добавить бота на окно     [P] Пауза / Возобновить бота")
        print("   [S] Остановить конкретного бота           [K] Остановить ВСЕХ ботов")
        print("   [T] Тестовый спин (1000 ₽ на 1 спин)      [C] Калибратор координат")
        print("   [M] Меню эмуляторов MuMu                  [Q] Завершить работу и выйти")
        print("=" * 88)

    def action_add_bot(self):
        """Adds and launches a bot on a selected instance without disturbing others."""
        devices = self.get_detected_devices()
        if not devices:
            self.last_status_msg = "Ошибка: не найдено доступных устройств MuMu."
            return

        print("\n" + "=" * 60)
        print("           ДОБАВЛЕНИЕ И ЗАПУСК БОТА НА ОКНЕ")
        print("=" * 60)

        # Show devices
        avail = []
        for k, v in sorted(devices.items(), key=lambda x: int(x[0])):
            idx = int(k)
            name = v.get("name", f"Instance {idx}")
            is_run = v.get("is_android_started", False)
            bot_exists = (idx in self.active_bots and self.active_bots[idx].is_alive())
            status = "Уже в игре" if bot_exists else ("Запущен в MuMu" if is_run else "Выключен в MuMu")
            print(f"  [#{idx}] {name} ({status})")
            if not bot_exists:
                avail.append(idx)

        if not avail:
            print("[!] На всех устройствах уже запущены боты!")
            input("Нажмите Enter для возврата...")
            return

        def_idx = avail[0]
        idx_in = input(f"\nВыберите номер окна (#) [по умолчанию {def_idx}] (или 'b' для отмены): ").strip()
        if idx_in.lower() in ('b', 'back', 'q', 'exit', 'отмена'):
            return

        try:
            vm_idx = int(idx_in) if idx_in else def_idx
        except ValueError:
            self.last_status_msg = "Некорректный номер окна."
            return

        dev_info = devices.get(str(vm_idx), {})
        dev_name = dev_info.get("name", f"Instance {vm_idx}")
        is_started = dev_info.get("is_android_started", False)

        if not is_started:
            start_in = input(f"Окно #{vm_idx} '{dev_name}' сейчас выключено. Запустить его в MuMu? [Y/n/b]: ").strip().lower()
            if start_in in ('b', 'back', 'отмена'):
                return
            if start_in not in ('n', 'no', 'нет'):
                print(f"[*] Запускаем устройство #{vm_idx}... Ожидайте 10-15 сек...")
                MuMuManagerCLI.launch_instance(vm_idx)
                for _ in range(12):
                    time.sleep(1.0)
                    fresh = self.get_detected_devices()
                    if fresh.get(str(vm_idx), {}).get("is_android_started", False):
                        dev_info = fresh[str(vm_idx)]
                        break

        port = dev_info.get("adb_port", 16384 + vm_idx * 32)

        # Bankroll
        b_in = input(f"Стартовый баланс в RUB [1000000] (или 'b' для отмены): ").strip()
        if b_in.lower() in ('b', 'back', 'отмена'):
            return
        try:
            bankroll = int(b_in.replace(" ", "").replace(",", "")) if b_in else 1_000_000
        except ValueError:
            bankroll = 1_000_000

        # Mode
        print("\nВыберите режим игры (v15.1 Commercial Farm Release):")
        print("  0) [БЕТА-ТЕСТ] Безопасная тестовая крутка со ставкой ровно 1 000 ₽")
        print("  1) APEX_FARM           - Идеальный баланс для фермы (Основной AFK, N=8/10/10)")
        print("  2) TURBO_VELOCITY      - Спринт / Высокий доход (Умеренный азарт, N=8/9/10)")
        print("  3) SHIELD_FORTRESS     - Максимальная броня (Для малых банков, N=10 + Micro-Harvest)")
        p_in = input("Выберите [0/1/2/3, по умолчанию 0]: ").strip()
        if p_in.lower() in ('b', 'back', 'отмена'):
            return

        flat_mode = (p_in == "0" or p_in == "")
        profile: StrategyProfile = 'APEX_IDEAL'
        if p_in == "2":
            profile = 'TURBO_HARVEST'
        elif p_in == "3":
            profile = 'SHIELD_CONSERVATIVE'

        config = BotConfig(
            device_serial=f"127.0.0.1:{port}",
            initial_bankroll=bankroll,
            strategy_profile=profile,
            min_balance_threshold=2_000_000,
            flat_bet_mode=flat_mode,
            flat_bet_amount=1000,
            fast_mode=True
        )

        bot_inst = ActiveBotInstance(vm_idx, dev_name, port, config)
        self.active_bots[vm_idx] = bot_inst
        bot_inst.start()

        self.last_status_msg = f"Бот #{vm_idx} '{dev_name}' успешно запущен в фоновом режиме!"

    def action_pause_resume(self):
        """Toggles pause/resume on selected bot or all bots."""
        if not self.active_bots:
            self.last_status_msg = "Нет активных ботов для паузы."
            return

        print("\n" + "=" * 60)
        print("            ПАУЗА / ВОЗОБНОВЛЕНИЕ БОТОВ")
        print("=" * 60)
        for idx, inst in sorted(self.active_bots.items()):
            state = "НА ПАУЗЕ" if inst.telemetry.get("is_paused") else "РАБОТАЕТ"
            print(f"  [#{idx}] {inst.name} | Состояние: {state}")

        p_in = input("\nВведите номер бота (#) или 'all' для переключения [all]: ").strip().lower()
        if p_in in ('b', 'back', 'отмена'):
            return

        if p_in in ('all', '', 'все'):
            # Toggle all
            any_running = any(not b.telemetry.get("is_paused") for b in self.active_bots.values())
            for b in self.active_bots.values():
                if any_running:
                    b.pause()
                else:
                    b.resume()
            self.last_status_msg = "Все боты переведены на ПАУЗУ." if any_running else "Все боты ВОЗОБНОВИЛИ работу."
        else:
            try:
                target_idx = int(p_in)
                if target_idx in self.active_bots:
                    b = self.active_bots[target_idx]
                    if b.telemetry.get("is_paused"):
                        b.resume()
                        self.last_status_msg = f"Бот #{target_idx} ВОЗОБНОВИЛ работу."
                    else:
                        b.pause()
                        self.last_status_msg = f"Бот #{target_idx} переведен на ПАУЗУ."
                else:
                    self.last_status_msg = f"Бот #{target_idx} не найден."
            except ValueError:
                self.last_status_msg = "Неверный ввод."

    def action_stop_bot(self):
        """Stops a specific bot without stopping others."""
        if not self.active_bots:
            self.last_status_msg = "Нет запущенных ботов."
            return

        print("\n" + "=" * 60)
        print("               ОСТАНОВКА КОНКРЕТНОГО БОТА")
        print("=" * 60)
        for idx, inst in sorted(self.active_bots.items()):
            print(f"  [#{idx}] {inst.name} (Порт: {inst.port}) | Спинов: {inst.telemetry.get('spin', 0)}")

        s_in = input("\nВведите номер бота (#) для остановки (или 'b' для отмены): ").strip()
        if s_in.lower() in ('b', 'back', 'отмена'):
            return

        try:
            idx = int(s_in)
            if idx in self.active_bots:
                inst = self.active_bots[idx]
                inst.stop()
                self.last_status_msg = f"Бот #{idx} '{inst.name}' остановлен. Отчет сохранен в bot/logs/."
            else:
                self.last_status_msg = f"Бот #{idx} не найден среди активных."
        except ValueError:
            self.last_status_msg = "Некорректный номер бота."

    def action_stop_all(self):
        """Stops all active bots cleanly."""
        if not self.active_bots:
            self.last_status_msg = "Нет активных ботов."
            return
        for b in self.active_bots.values():
            b.stop()
        self.last_status_msg = "Все боты успешно остановлены. Сессии сохранены в bot/logs/."

    def action_test_spin(self):
        """Performs 1 single test spin on a device."""
        devices = self.get_detected_devices()
        active = [int(k) for k, v in devices.items() if v.get("is_android_started", False)]
        def_idx = active[0] if active else 0

        print("\n" + "=" * 60)
        print("           ТЕСТОВЫЙ ОДИНОЧНЫЙ СПИН (1 000 ₽)")
        print("=" * 60)
        idx_in = input(f"Выберите номер окна (#) [по умолчанию {def_idx}]: ").strip()
        if idx_in.lower() in ('b', 'back', 'отмена'):
            return

        target_idx = int(idx_in) if idx_in else def_idx
        port = devices.get(str(target_idx), {}).get("adb_port", 16384 + target_idx * 32)

        print(f"[*] Выполняем одиночный спин на 127.0.0.1:{port}...")
        from bot.calibrate import CasinoCalibrator
        cal = CasinoCalibrator(serial=f"127.0.0.1:{port}")
        _, pts = cal.capture_and_annotate()
        if pts:
            ok = cal.test_full_spin(pts, 1000, 'RED')
            self.last_status_msg = "Тестовый спин успешно выполнен!" if ok else "Ошибка тестового спина."
        else:
            self.last_status_msg = "Диалог рулетки не обнаружен на экране!"
        time.sleep(1.5)

    def action_calibrate(self):
        """Launches interactive calibrator."""
        from bot.calibrate import run_interactive_menu
        run_interactive_menu()
        self.last_status_msg = "Калибровка завершена."

    def action_mumu_menu(self):
        """MuMu emulator management submenu."""
        clear_screen()
        print("=" * 60)
        print("             УПРАВЛЕНИЕ ЭМУЛЯТОРАМИ MUMU PLAYER 12")
        print("=" * 60)
        print(" [1] Запустить окно эмулятора")
        print(" [2] Клонировать окно (Создать нового бота с игрой)")
        print(" [3] Выровнять окна сеткой на мониторе (Sort)")
        print(" [B] Назад в центр управления")
        print("=" * 60)
        m_in = input("Выберите действие [1/2/3/B]: ").strip().lower()

        if m_in == "1":
            idx_in = input("Номер окна для запуска [0]: ").strip()
            if idx_in:
                MuMuManagerCLI.launch_instance(int(idx_in))
                self.last_status_msg = f"Команда запуска окна #{idx_in} отправлена."
        elif m_in == "2":
            src = input("Клонировать с какого окна? [0]: ").strip()
            src_idx = int(src) if src else 0
            name = input("Имя нового окна [Farm_Device]: ").strip() or "Farm_Device"
            print("[*] Клонирование... Пожалуйста, подождите 15-30 сек...")
            ok = MuMuManagerCLI.clone_instance(src_idx, name)
            self.last_status_msg = "Клонирование успешно завершено!" if ok else "Ошибка клонирования."
        elif m_in == "3":
            MuMuManagerCLI.arrange_windows_grid()
            self.last_status_msg = "Окна MuMu выровнены сеткой на мониторе."

    def handle_command(self, cmd: str):
        """Dispatches key command to corresponding interactive action."""
        cmd = cmd.strip().lower()
        if cmd == 'a':
            self.action_add_bot()
        elif cmd == 'p':
            self.action_pause_resume()
        elif cmd == 's':
            self.action_stop_bot()
        elif cmd == 'k':
            self.action_stop_all()
        elif cmd == 't':
            self.action_test_spin()
        elif cmd == 'c':
            self.action_calibrate()
        elif cmd == 'm':
            self.action_mumu_menu()
        elif cmd in ('q', 'quit', 'exit', 'й'):
            self.is_running = False

    def run(self):
        """Main non-blocking interactive application loop."""
        def sig_handler(sig, frame):
            self.is_running = False

        old_sig = signal.signal(signal.SIGINT, sig_handler)

        try:
            while self.is_running:
                self.render_screen()

                # Sleep in small slices, checking for user keystrokes non-blockingly
                for _ in range(8): # 8 * 0.1s = 0.8s refresh rate
                    if not self.is_running:
                        break
                    key = self._read_key()
                    if key:
                        self.handle_command(key)
                        break
                    time.sleep(0.1)

                # Fallback if msvcrt is not available or stdin is interactive
                if not HAS_MSVCRT and self.is_running:
                    cmd = input("\nВведите команду [A/P/S/K/T/C/M/Q]: ")
                    self.handle_command(cmd)

        finally:
            print("\n[*] Завершаем работу ботов и сохраняем отчеты сессий...")
            for idx, inst in self.active_bots.items():
                inst.stop()
            time.sleep(0.5)
            print("[+] Все отчеты сессий успешно сохранены в bot/logs/!")
            signal.signal(signal.SIGINT, old_sig)

if __name__ == "__main__":
    app = MasterDashboard()
    app.run()
