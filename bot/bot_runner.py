"""
Main Interactive & CLI Runner for Matreshka RP Casino Automation Bot.
Usage:
    python bot/bot_runner.py
    python bot/bot_runner.py --port 16384 --balance 3800000 --profile APEX_IDEAL
"""

import sys
import os
import argparse
import signal
import time

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from bot.config import BotConfig, StrategyProfile
from bot.state_machine import CasinoBot
from bot.adb_controller import ADBController

def prompt_user_config() -> BotConfig:
    print("\n" + "="*50)
    print("      МАТРЁШКА RP - CASINO AUTOMATION ENGINE")
    print("      v15.0 FINAL APEX • Auto-Pilot Bot")
    print("="*50 + "\n")

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
    print("\n[*] Выберите режим работы:")
    print("    0) [БЕТА-ТЕСТ] Безопасный тест механики (ФИКСИРОВАННАЯ ставка ровно 1 000 ₽)")
    print("    1) APEX_IDEAL          - Сбалансированный боевой режим (Рекомендуется)")
    print("    2) TURBO_HARVEST       - Максимальная агрессивная доходность")
    print("    3) SHIELD_CONSERVATIVE - Максимальная защита от глубоких просадок")
    p_choice = input("    Выберите [0/1/2/3, по умолчанию 0 для теста]: ").strip()
    
    flat_mode = False
    profile: StrategyProfile = 'APEX_IDEAL'
    if p_choice == "0" or p_choice == "":
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

    return BotConfig(
        device_serial=serial,
        initial_bankroll=initial_bank,
        strategy_profile=profile,
        fast_mode=fast_mode,
        flat_bet_mode=flat_mode,
        flat_bet_amount=1000
    )

def main():
    parser = argparse.ArgumentParser(description="Matreshka RP Casino AFK Automation Bot")
    parser.add_argument("--port", type=str, default=None, help="ADB Serial or Port (e.g. 16384 or 127.0.0.1:16384)")
    parser.add_argument("--balance", type=int, default=None, help="Initial bankroll in RUB")
    parser.add_argument("--profile", type=str, choices=['APEX_IDEAL', 'TURBO_HARVEST', 'SHIELD_CONSERVATIVE'], default='APEX_IDEAL')
    parser.add_argument("--test-flat", action="store_true", default=False, help="Enable safe beta-test flat bet mode (1000 RUB only)")
    parser.add_argument("--fast", action="store_true", default=True, help="Enable fast mechanical betting")
    parser.add_argument("--take-profit", type=int, default=None, help="Take-profit target amount in RUB")
    parser.add_argument("--stop-loss-pct", type=float, default=0.50, help="Stop-loss ratio (e.g. 0.50 = 50%)")

    args = parser.parse_args()

    # If arguments provided via CLI, use them; otherwise interactive wizard
    if args.balance is not None:
        serial = args.port or "127.0.0.1:16384"
        if not ":" in serial:
            serial = f"127.0.0.1:{serial}"
        config = BotConfig(
            device_serial=serial,
            initial_bankroll=args.balance,
            strategy_profile=args.profile,
            fast_mode=args.fast,
            flat_bet_mode=args.test_flat,
            flat_bet_amount=1000,
            take_profit_target=args.take_profit,
            stop_loss_pct=args.stop_loss_pct
        )
    else:
        config = prompt_user_config()

    bot = CasinoBot(config)

    # Graceful shutdown on Ctrl+C
    def handle_sigint(sig, frame):
        print("\n\n[INFO] Получен сигнал прерывания (Ctrl+C). Корректно завершаем сессию...")
        bot.stop()

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        bot.run()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
