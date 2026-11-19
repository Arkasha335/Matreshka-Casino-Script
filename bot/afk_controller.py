"""
AFK Controller & Auto-Sleep Module for Matreshka RP Casino Bot.
Manages scheduled sessions, AFK timers, graceful series completions,
and safe PC sleep mode / standby transitions.
"""

import sys
import os
import time
import re
import datetime
import threading
from typing import Optional, Callable

# Windows API for system sleep
if os.name == 'nt':
    import ctypes
    try:
        import msvcrt
        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False
else:
    HAS_MSVCRT = False


def parse_time_spec(spec: str) -> Optional[float]:
    """
    Parses duration or time-of-day string into target epoch timestamp.
    Examples:
        '30m'  -> 30 minutes from now
        '2h'   -> 2 hours from now
        '1.5h' -> 90 minutes from now
        '90'   -> 90 minutes from now
        '04:30'-> 04:30 AM (today or tomorrow)
        '23:15'-> 23:15 (today or tomorrow)
    """
    if not spec:
        return None
    spec = spec.strip().lower()

    # 1. Exact clock time: HH:MM or H:MM
    clock_match = re.match(r"^(\d{1,2}):(\d{2})$", spec)
    if clock_match:
        target_h = int(clock_match.group(1))
        target_m = int(clock_match.group(2))
        if 0 <= target_h <= 23 and 0 <= target_m <= 59:
            now = datetime.datetime.now()
            target_dt = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
            if target_dt <= now:
                # If target time is earlier today, schedule for tomorrow
                target_dt += datetime.timedelta(days=1)
            return target_dt.timestamp()

    # 2. Relative duration: e.g. 2h, 90m, 45s, 1.5h
    dur_match = re.match(r"^([\d\.]+)\s*([hmsчмс]?)$", spec)
    if dur_match:
        val = float(dur_match.group(1))
        unit = dur_match.group(2)
        if unit in ('h', 'ч'):
            sec = val * 3600
        elif unit in ('s', 'с'):
            sec = val
        else: # Default is minutes ('m', 'м', or no unit)
            sec = val * 60
        return time.time() + sec

    return None


class AFKController:
    """
    Monitors session runtime against an AFK duration or target hour.
    Coordinates graceful series shutdown and subsequent PC standby/sleep.
    """
    def __init__(
        self,
        target_timestamp: Optional[float] = None,
        sleep_pc_on_stop: bool = False,
        close_emulators_on_stop: bool = True
    ):
        self.target_timestamp = target_timestamp
        self.sleep_pc_on_stop = sleep_pc_on_stop
        self.close_emulators_on_stop = close_emulators_on_stop
        self.is_active = target_timestamp is not None
        self.has_triggered_stop = False

    def set_timer(self, spec: str, sleep_pc: bool = False):
        """Sets or updates the AFK target timer from a user spec."""
        target = parse_time_spec(spec)
        if target:
            self.target_timestamp = target
            self.sleep_pc_on_stop = sleep_pc
            self.is_active = True
            self.has_triggered_stop = False
            return True
        return False

    def disable(self):
        """Disables the AFK timer."""
        self.is_active = False
        self.target_timestamp = None
        self.has_triggered_stop = False

    def is_expired(self) -> bool:
        """Returns True if the scheduled time has elapsed."""
        if not self.is_active or self.target_timestamp is None:
            return False
        return time.time() >= self.target_timestamp

    def get_remaining_seconds(self) -> Optional[float]:
        """Returns remaining seconds until AFK stop, or None if disabled."""
        if not self.is_active or self.target_timestamp is None:
            return None
        return max(0.0, self.target_timestamp - time.time())

    def format_remaining(self) -> str:
        """Formats remaining time as HH:MM:SS."""
        rem = self.get_remaining_seconds()
        if rem is None:
            return "ОТКЛЮЧЕН"
        total = int(rem)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def format_target_clock(self) -> str:
        """Formats target time as HH:MM:SS."""
        if not self.target_timestamp:
            return "—"
        dt = datetime.datetime.fromtimestamp(self.target_timestamp)
        return dt.strftime("%H:%M:%S")

    def execute_pc_sleep(self, countdown_sec: int = 15, abort_key_check: bool = True) -> bool:
        """
        Puts Windows PC into Sleep Mode (Standby) after countdown.
        Allows the user to abort by pressing any key during countdown.
        """
        if os.name != 'nt':
            print("[AFK] Переход в спящий режим поддерживается только на Windows.")
            return False

        print("\n" + "=" * 65)
        print(" [АВТО-ВЫКЛЮЧЕНИЕ] СЕССИЯ УСПЕШНО ЗАКРЫТА БЕЗ ДОЛГОВ!")
        print(f" Компьютер перейдет в СПЯЩИЙ РЕЖИМ через {countdown_sec} секунд...")
        print(" Нажмите [ЛЮБУЮ КЛАВИШУ] или Ctrl+C в консоли для отмены сна.")
        print("=" * 65 + "\n")

        cancelled = False
        for sec_left in range(countdown_sec, 0, -1):
            sys.stdout.write(f"\r >> До перехода в спящий режим: {sec_left} сек... [Нажмите любую клавишу для отмены] ")
            sys.stdout.flush()

            if abort_key_check and HAS_MSVCRT:
                if msvcrt.kbhit():
                    msvcrt.getch()
                    cancelled = True
                    break

            time.sleep(1.0)

        sys.stdout.write("\n")
        if cancelled:
            print("\n[+] Спящий режим ОТМЕНЁН пользователем. Компьютер продолжает работу.")
            return False

        print("\n[*] Завершаем системные службы и переводим ПК в спящий режим...")
        time.sleep(1.0)

        try:
            # SetSuspendState(bHibernate=0, bForce=1, bWakeupEventsDisabled=0)
            # bHibernate=0 -> Standby (Sleep)
            ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
            return True
        except Exception as e:
            # Fallback to shell invocation
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return True
