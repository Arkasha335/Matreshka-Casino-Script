"""
Main Interactive & CLI Runner for Matreshka RP Casino Automation Bot.
v16.1 APEX-Neural Edition with Safe Debt-Free Shutdown and AFK Auto-Sleep.

Usage:
    python bot/bot_runner.py
    python bot/bot_runner.py --balance 1000000 --profile APEX_IDEAL --duration 2h --sleep-pc
    python bot/bot_runner.py --balance 3500000 --until 04:30 --sleep-pc
"""

import sys
import os
import argparse
import signal
import time
import threading

# Windows non-blocking keyboard support
if os.name == 'nt':
    try:
        import msvcrt
        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False
else:
    HAS_MSVCRT = False

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from bot.config import BotConfig, StrategyProfile
from bot.state_machine import CasinoBot
from bot.adb_controller import ADBController
from bot.afk_controller import parse_time_spec


def prompt_user_config() -> BotConfig:
    print("\n" + "=" * 55)
    print("      МАТРЁШКА RP - CASINO AUTOMATION ENGINE")
    print("      v16.1 APEX-NEURAL • Auto-Pilot & AFK Farm")
    print("=" * 55 + "\n")

    # 1. Device port
    default_serial = ADBController.get_best_active_serial()
    print(f"[*] Эмулятор ADB Port [авто-обнаружен активный: {default_serial}]:")
    port_in = input("    Введите порт или Enter для значения по умолчанию: ").strip()
    if not port_in:
        serial = default_serial
    elif ":" in port_in:
        serial = port_in
    else:
        serial = f"127.0.0.1:{port_in}"

    # 2. Initial Bankroll
    while True:
        try:
            b_in = input("\n[*] Введите начальный баланс аккаунта в RUB (например, 1000000): ").strip()
            initial_bank = int(b_in.replace(" ", "").replace("_", "").replace(",", ""))
            if initial_bank < 1000:
                print("    Минимальный баланс для работы стратегии — 1 000 RUB.")
                continue
            break
        except ValueError:
            print("    Пожалуйста, введите корректное целое число.")

    # 3. Strategy profile & Test Mode
    print("\n[*] Выберите режим работы (v16.1 APEX-Neural):")
    print("    0) [БЕТА-ТЕСТ] Безопасный тест механики (ФИКСИРОВАННАЯ ставка ровно 1 000 ₽)")
    print("    1) APEX_IDEAL          - Сбалансированный боевой режим (Рекомендуется)")
    print("    2) TURBO_HARVEST       - Максимальная агрессивная доходность")
    print("    3) SHIELD_CONSERVATIVE - Максимальная защита от глубоких просадок")
    p_choice = input("    Выберите [0/1/2/3, по умолчанию 1]: ").strip()

    flat_mode = False
    profile: StrategyProfile = 'APEX_IDEAL'
    if p_choice == "0":
        flat_mode = True
        profile = 'APEX_IDEAL'
    elif p_choice == "2":
        profile = 'TURBO_HARVEST'
    elif p_choice == "3":
        profile = 'SHIELD_CONSERVATIVE'
    else:
        profile = 'APEX_IDEAL'

    # 4. Fast mode
    fast_in = input("\n[*] Включить быстрый механический режим ставок? [Y/n]: ").strip().lower()
    fast_mode = fast_in not in ("n", "no", "нет")

    # 5. AFK Timer & PC Sleep
    print("\n[*] Настройка АФК-таймера и автовыключения:")
    afk_in = input("    Задать время работы (например, 2h, 90m, 05:00 или Enter для игры без таймера): ").strip()
    sleep_pc = False
    if afk_in:
        sleep_in = input("    Перевести ПК в СПЯЩИЙ РЕЖИМ после закрытия серии? [y/N]: ").strip().lower()
        sleep_pc = sleep_in in ("y", "yes", "да", "д")

    return BotConfig(
        device_serial=serial,
        initial_bankroll=initial_bank,
        strategy_profile=profile,
        fast_mode=fast_mode,
        flat_bet_mode=flat_mode,
        flat_bet_amount=1000,
        afk_duration_str=afk_in if afk_in else None,
        sleep_pc_on_stop=sleep_pc
    )


def start_keyboard_listener(bot: CasinoBot):
    """
    Background thread that listens for non-blocking hotkeys in console:
      [Q] - Безопасная остановка (доиграть серию до CDT=0)
      [P] - Пауза / Возобновление
      [S] - Статус и прогресс
      [Z] - Переключение режима сна ПК
    """
    if not HAS_MSVCRT:
        return

    def _listen():
        while bot.is_running:
            try:
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    key = ch.decode('utf-8', errors='ignore').lower()

                    if key in ('q', 'й'):
                        print("\n\n" + "=" * 55)
                        print(" [ГОРЯЧАЯ КЛАВИША 'Q']: Запрос БЕЗОПАСНОЙ остановки!")
                        print(f" Бот доиграет текущую серию (Шаг {bot.current_step}, Долг {bot.cdt:,.0f} ₽) и затем завершит работу.")
                        print("=" * 55 + "\n")
                        bot.request_graceful_stop("Остановка по клавише 'Q'")

                    elif key in ('p', 'з'):
                        if bot.is_paused:
                            print("\n[ГОРЯЧАЯ КЛАВИША 'P']: Возобновление игры...")
                            bot.resume()
                        else:
                            print("\n[ГОРЯЧАЯ КЛАВИША 'P']: Сессия поставлена на ПАУЗУ.")
                            bot.pause()

                    elif key in ('s', 'ы'):
                        print("\n" + "-" * 55)
                        print(f" [ТЕКУЩИЙ СТАТУС БОТА v16.1]")
                        print(f" Баланс: {bot.bankroll:,.0f} ₽ (Профит: {bot.bankroll - bot.initial_bankroll:+,.0f} ₽)")
                        print(f" Серия: Шаг {bot.current_step} | Долг CDT: {bot.cdt:,.0f} ₽ | Режим: {bot.current_mode}")
                        wr = (bot.wins / max(1, bot.spin_index)) * 100
                        print(f" Винрейт: {bot.wins} В / {bot.losses} П ({wr:.1f}%) | Спинов: {bot.spin_index}")
                        if bot.afk.is_active:
                            print(f" Таймер АФК: осталось {bot.afk.format_remaining()} (до {bot.afk.format_target_clock()})")
                            print(f" Спящий режим ПК: {'ВКЛЮЧЕН' if bot.afk.sleep_pc_on_stop else 'ВЫКЛЮЧЕН'}")
                        if bot.graceful_stop_requested:
                            print(f" СТАТУС ОСТАНОВКИ: ОЖИДАНИЕ ЗАКРЫТИЯ СЕРИИ (CDT={bot.cdt:,.0f} ₽)")
                        print("-" * 55 + "\n")

                    elif key in ('z', 'я'):
                        bot.afk.sleep_pc_on_stop = not bot.afk.sleep_pc_on_stop
                        state_str = "ВКЛЮЧЕН" if bot.afk.sleep_pc_on_stop else "ВЫКЛЮЧЕН"
                        print(f"\n[ГОРЯЧАЯ КЛАВИША 'Z']: Спящий режим ПК после завершения: {state_str}")

            except Exception:
                pass
            time.sleep(0.15)

    t = threading.Thread(target=_listen, daemon=True)
    t.start()


def main():
    parser = argparse.ArgumentParser(description="Matreshka RP Casino AFK Automation Bot v16.1")
    parser.add_argument("--port", type=str, default=None, help="ADB Serial or Port (e.g. 16384 or 127.0.0.1:16384)")
    parser.add_argument("--balance", type=int, default=None, help="Initial bankroll in RUB")
    parser.add_argument("--profile", type=str, choices=['APEX_IDEAL', 'TURBO_HARVEST', 'SHIELD_CONSERVATIVE'], default='APEX_IDEAL')
    parser.add_argument("--test-flat", action="store_true", default=False, help="Enable safe beta-test flat bet mode (1000 RUB only)")
    parser.add_argument("--fast", action="store_true", default=True, help="Enable fast mechanical betting")
    parser.add_argument("--take-profit", type=int, default=None, help="Take-profit target amount in RUB")
    parser.add_argument("--stop-loss-pct", type=float, default=0.50, help="Stop-loss ratio (e.g. 0.50 = 50%)")
    parser.add_argument("--duration", type=str, default=None, help="AFK duration (e.g. 2h, 90m, 120)")
    parser.add_argument("--until", type=str, default=None, help="Stop at clock time (e.g. 04:30, 23:00)")
    parser.add_argument("--sleep-pc", action="store_true", default=False, help="Put Windows PC into Sleep mode after graceful series completion")

    args = parser.parse_args()

    # Determine AFK spec
    afk_spec = args.duration or args.until

    if args.balance is not None:
        serial = args.port or "127.0.0.1:16384"
        if ":" not in serial:
            serial = f"127.0.0.1:{serial}"
        config = BotConfig(
            device_serial=serial,
            initial_bankroll=args.balance,
            strategy_profile=args.profile,
            fast_mode=args.fast,
            flat_bet_mode=args.test_flat,
            flat_bet_amount=1000,
            take_profit_target=args.take_profit,
            stop_loss_pct=args.stop_loss_pct,
            afk_duration_str=afk_spec,
            sleep_pc_on_stop=args.sleep_pc
        )
    else:
        config = prompt_user_config()

    bot = CasinoBot(config)

    # Double Ctrl+C protection:
    # 1st press = Graceful Stop (finishes debt/series)
    # 2nd press = Emergency Force Stop
    ctrl_c_count = 0

    def handle_sigint(sig, frame):
        nonlocal ctrl_c_count
        ctrl_c_count += 1
        if ctrl_c_count == 1:
            if bot.cdt > 0 or bot.current_step > 1:
                print("\n\n" + "!" * 62)
                print(" [Ctrl+C] ПОЛУЧЕН СИГНАЛ ОСТАНОВКИ!")
                print(f" [БЕЗОПАСНЫЙ РЕЖИМ]: Активна серия (Шаг {bot.current_step}, Долг {bot.cdt:,.0f} ₽).")
                print(" Бот ДОИГРАЕТ текущую серию до победы/сброса, чтобы НЕ ПОТЕРЯТЬ ДОЛГ!")
                print(" Нажмите Ctrl+C повторно прямо сейчас для ЭКСТРЕННОГО немедленного выхода.")
                print("!" * 62 + "\n")
                bot.request_graceful_stop("Остановка по сигналу Ctrl+C")
            else:
                print("\n\n[INFO] Получен сигнал прерывания (Ctrl+C). Долгов нет (CDT=0). Чистый выход...")
                bot.stop(force=True)
        else:
            print("\n\n[ВНИМАНИЕ] ПОВТОРНЫЙ Ctrl+C! ЭКСТРЕННАЯ ПРИНУДИТЕЛЬНАЯ ОСТАНОВКА!")
            bot.stop(force=True)
            sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    # Print hotkey tips
    if HAS_MSVCRT:
        print("\n" + "=" * 55)
        print(" [ГОРЯЧИЕ КЛАВИШИ В ТЕРМИНАЛЕ]:")
        print("   [Q] - Безопасная остановка (доиграть серию до CDT=0)")
        print("   [P] - Пауза / Возобновление")
        print("   [S] - Статус сессии и таймера")
        print("   [Z] - Вкл/выкл спящий режим ПК после завершения")
        print("=" * 55 + "\n")
        start_keyboard_listener(bot)

    try:
        bot.run()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
