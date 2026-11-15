"""
State Machine module for the Matreshka RP Casino Automation Bot.
Orchestrates betting cycles, v15.0 engine calculations, PayDay dismissal,
spin waiting, outcome extraction, and risk management.
"""

import time
import os
import sys
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

# Ensure parent directory is on sys.path for engine_mirror import
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.audit.engine_mirror import (
    PrngDetectorMirror,
    BankrollManagerMirror,
    GAME_RULES,
    js_round
)

from .config import BotConfig, Outcome, ServerMode
from .adb_controller import ADBController
from .vision_engine import VisionEngine
from .session_logger import SessionLogger
from .apex_engine import ApexEngineClient

class CasinoBot:
    def __init__(
        self,
        config: BotConfig,
        on_status_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        silent: bool = False,
        device_name: str = "Android Device"
    ):
        self.config = config
        self.on_status_update = on_status_update
        self.silent = silent
        self.device_name = device_name
        self.adb = ADBController(serial=config.device_serial, adb_path=config.adb_path)
        self.vision = VisionEngine(templates_dir=config.templates_dir)
        self.logger = SessionLogger(logs_dir=config.logs_dir)
        self.engine = ApexEngineClient()

        # State tracking (100% matched to Next.js lib/engine and app/page.tsx)
        self.bankroll = config.initial_bankroll
        self.initial_bankroll = config.initial_bankroll
        self.peak_bankroll = config.initial_bankroll
        self.max_drawdown = 0
        self.wins = 0
        self.losses = 0
        self.history: List[Outcome] = []
        self.engine_history: List[Dict[str, Any]] = []
        self.current_step = 1
        self.cdt = 0 # Cumulative debt tracker
        self.zero_in_sequence = 0
        self.current_mode: ServerMode = 'ZEBRA'
        self.previous_mode: ServerMode = 'ZEBRA'
        self.spins_since_danger_exit = 999
        self.spins_in_current_mode = 0
        self.sequence_start_mode: ServerMode = 'ZEBRA'
        self.sequence_target_steps: Optional[int] = None
        self.last_prediction: Dict[str, Any] = {}
        self.stats: Dict[str, Any] = {}
        self.prev_bet_amount = 0
        self.spin_index = 0
        self.is_running = False
        self.is_paused = False
        self.last_winning_num = -1
        self.last_event = "Инициализация"
        self.start_time = time.time()
        self.stop_reason: Optional[str] = None
        self.current_state = "IDLE"
        self.current_bet_in_field: Optional[int] = None

    def _calc_net_win(self, bet: int) -> int:
        """Calculates net win with 2% server tax: round(bet * 98 / 100)."""
        return js_round(bet * 0.98)

    def _log(self, msg: str):
        if not self.silent:
            print(msg)

    def _emit_status(self, state: str, extra: Optional[Dict[str, Any]] = None):
        """Sends rich live telemetry to runner/dashboard."""
        self.current_state = state
        if extra and "msg" in extra:
            self.last_event = extra["msg"]
        elif extra and "event" in extra:
            self.last_event = extra["event"]

        win_rate = self.stats.get("winRate", round((self.wins / self.spin_index * 100), 1) if self.spin_index > 0 else 0.0)
        profit = self.bankroll - self.initial_bankroll
        peak = self.stats.get("peakBankroll", self.bankroll)
        max_dd = self.stats.get("maxDrawdown", self.max_drawdown)
        eff_mode = self.last_prediction.get("effectiveMode", self.current_mode)

        data = {
            "device_name": self.device_name,
            "serial": self.config.device_serial,
            "state": state,
            "is_paused": self.is_paused,
            "spin": self.spin_index,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(win_rate, 1),
            "initial_bankroll": self.initial_bankroll,
            "bankroll": self.bankroll,
            "profit": profit,
            "peak_bankroll": peak,
            "max_drawdown": max_dd,
            "step": self.current_step,
            "cdt": self.cdt,
            "mode": eff_mode,
            "raw_mode": self.current_mode,
            "is_zero_shock": self.last_prediction.get("isZeroShock", False),
            "is_zebra_locked": self.last_prediction.get("isZebraLocked", False),
            "recommendation_state": self.last_prediction.get("state", "АНАЛИЗ"),
            "confidence": self.last_prediction.get("confidence", 50),
            "history_len": len(self.history),
            "color_history": list(self.history[-40:]),
            "last_win_num": self.last_winning_num,
            "last_event": self.last_event,
            "stop_reason": self.stop_reason,
            "uptime_sec": int(time.time() - self.start_time),
            "detailed_stats": self.stats
        }
        if extra:
            data.update(extra)

        if self.on_status_update:
            self.on_status_update(data)

    def pause(self):
        """Pauses betting activity cleanly."""
        self.is_paused = True
        self.last_event = "Сессия приостановлена (ПАУЗА)"
        self._emit_status("PAUSED", {"msg": self.last_event})

    def resume(self):
        """Resumes betting activity."""
        self.is_paused = False
        self.last_event = "Сессия возобновлена (РАБОТА)"
        self._emit_status("RESUMED", {"msg": self.last_event})

    def is_active(self) -> bool:
        return self.is_running and not self.is_paused

    def handle_payday_if_present(self, scene) -> bool:
        """Checks and dismisses PayDay check modal if present."""
        is_payday, close_pt = self.vision.is_payday_popup_present(scene)
        if is_payday and close_pt:
            self.last_event = "PayDay проверка: окно закрыто по крестику [X]"
            self._emit_status("PAYDAY_DETECTED", {"msg": self.last_event})
            self.adb.tap(close_pt[0], close_pt[1], jitter=2)
            time.sleep(0.5)
            return True
        return False

    def _execute_bet_and_play(self, pts: Dict[str, Tuple[int, int]], rec_color: Outcome, bet_amount: int):
        """
        Executes color selection, bet amount input (if changed), and 'Играть' click.
        Uses batched atomic ADB command chain in fast_mode (<200ms).
        """
        target_cell = pts["red_cell"] if rec_color == 'RED' else pts["black_cell"]
        play_pt = pts["play_btn"]
        bet_changed = (self.current_bet_in_field != bet_amount)

        if self.config.fast_mode:
            self.adb.batched_bet(
                color_x=target_cell[0],
                color_y=target_cell[1],
                play_x=play_pt[0],
                play_y=play_pt[1],
                bet_amount=bet_amount if bet_changed else None,
                bet_input_pt=pts["bet_input"] if bet_changed else None,
                changed=bet_changed,
                jitter=1
            )
            self.current_bet_in_field = bet_amount
        else:
            self.adb.tap(target_cell[0], target_cell[1], jitter=1)
            time.sleep(0.05)
            if bet_changed:
                bet_pt = pts["bet_input"]
                self.adb.clear_and_type(bet_pt[0], bet_pt[1], str(bet_amount), backspaces=8, post_delay=0.05, press_enter=True)
                self.current_bet_in_field = bet_amount
                time.sleep(0.06)
            self.adb.tap(play_pt[0], play_pt[1], jitter=1)

    def run(self):
        """Main execution loop with robust pause, crash isolation, and live telemetry."""
        self.is_running = True
        self.start_time = time.time()
        self.last_event = "Поиск стола 'Красное и черное'..."
        self._emit_status("WAITING_TABLE", {"msg": self.last_event})

        self._log(f"\n==========================================")
        self._log(f" [MT CASINO BOT] Запуск AFK-сессии")
        self._log(f" Устройство: {self.config.device_serial}")
        self._log(f" Профиль: {self.config.strategy_profile} (Фикс 1000: {self.config.flat_bet_mode})")
        self._log(f" Начальный баланс: {self.bankroll:,.0f} ₽")
        self._log(f"==========================================\n")

        try:
            # Phase 1: Wait for table dialog to be open
            anchor = None
            while self.is_running:
                while self.is_paused and self.is_running:
                    time.sleep(0.3)
                if not self.is_running:
                    break

                scene = self.adb.screencap()
                if scene is None:
                    self.last_event = "Ошибка снятия скриншота ADB. Повтор..."
                    self._emit_status("ADB_RECONNECTING", {"msg": self.last_event})
                    time.sleep(2.0)
                    continue

                # Check and dismiss PayDay if popped up while waiting
                self.handle_payday_if_present(scene)

                anchor = self.vision.detect_casino_dialog(scene)
                if anchor:
                    self.last_event = "Стол 'Красное и черное' обнаружен!"
                    self._log(f"[OK] Стол обнаружен! Anchor: {anchor}")
                    self._emit_status("TABLE_READY", {"msg": self.last_event})
                    break
                else:
                    self.last_event = "Ожидание открытия диалога рулетки в игре..."
                    self._emit_status("WAITING_TABLE", {"msg": self.last_event})
                    time.sleep(1.5)

            # Pre-select "Точный цвет" tab initially
            if self.is_running and anchor:
                pts = self.vision.get_ui_click_points(anchor)
                tab_pt = pts["tab_exact_color"]
                self.adb.tap(tab_pt[0], tab_pt[1], jitter=2)
                time.sleep(0.3)

            # ------------------------------------------------------------------
            # Phase 2: Ultra-Fast Pipelined Betting Cycle
            # Zero redundant screencaps, zero redundant template searches,
            # immediate next-bet placement upon outcome detection (<250ms).
            # ------------------------------------------------------------------
            pts = self.vision.get_ui_click_points(anchor)

            # Spin #1: Initial Bet Computation
            calc = self.engine.calculate_bet(
                strategy_profile=self.config.strategy_profile,
                bankroll=self.bankroll,
                cdt=self.cdt,
                step=self.current_step,
                current_mode=self.current_mode,
                sequence_start_mode=self.sequence_start_mode,
                sequence_target_steps=self.sequence_target_steps,
                zero_in_sequence=self.zero_in_sequence,
                history=self.engine_history
            )
            self.last_prediction = calc
            next_bet = self.config.flat_bet_amount if self.config.flat_bet_mode else calc['bet']
            rec_color = calc['recommendation']
            eff_mode = calc['effectiveMode']

            if self.bankroll < next_bet:
                self.stop_reason = f"Недостаточно средств для ставки {next_bet:,.0f} ₽ (баланс: {self.bankroll:,.0f} ₽)"
                self.last_event = f"[БАЛАНС] Не хватает на ставку {next_bet:,.0f} ₽. Игра остановлена."
                self._log(f"\n[ALERT] {self.last_event}")
                self._emit_status("INSUFFICIENT_FUNDS", {"msg": self.last_event, "stop_reason": self.stop_reason})
                self.is_running = False

            if self.is_running:
                self.prev_bet_amount = next_bet
                self.last_event = f"Ставка {next_bet:,.0f} ₽ на {rec_color} (Шаг {self.current_step})"
                self._log(f"\n--- [СПИН #{self.spin_index + 1}] ---")
                self._log(f" Режим: {eff_mode} (Сырой: {self.current_mode}) | Шаг: {self.current_step} | CDT: {self.cdt:,.0f} ₽")
                self._log(f" Действие: {self.last_event}")

                self._emit_status("PLACING_BET", {
                    "bet": next_bet,
                    "color": rec_color,
                    "step": self.current_step,
                    "mode": eff_mode,
                    "msg": self.last_event
                })

                # Fire initial spin
                self._execute_bet_and_play(pts, rec_color, next_bet)
                spin_start_t = time.time()

                self.last_event = f"Вращение колеса... (Ставка {next_bet:,.0f} ₽ на {rec_color})"
                self._emit_status("SPINNING", {
                    "bet": next_bet,
                    "color": rec_color,
                    "msg": self.last_event
                })

            # Continuous Pipelined Spin-Outcome-Bet Loop
            while self.is_running:
                # 1. Quiet sleep while wheel physically spins (0% CPU)
                time.sleep(self.config.spin_sleep_sec)

                # 2. Dynamic high-speed scanning for outcome
                outcome_detected = False
                while self.is_running:
                    # Watchdog timeout check (40s safety)
                    if time.time() - spin_start_t > self.config.watchdog_timeout_sec:
                        self.last_event = "Watchdog: раунд завис более 40с. Сброс интерфейса..."
                        self._log(f"[WARN] {self.last_event}")
                        self._emit_status("WATCHDOG_TRIGGERED", {"msg": self.last_event})
                        break

                    scene_res = self.adb.screencap()
                    if scene_res is None:
                        time.sleep(self.config.poll_interval_sec)
                        continue

                    # Dismiss PayDay if popped up
                    self.handle_payday_if_present(scene_res)

                    # Fast ROI anchor check (<0.3ms); if failed, full template scan
                    if not self.vision.verify_dialog_anchor_fast(scene_res, anchor):
                        anchor = self.vision.detect_casino_dialog(scene_res)
                        if not anchor:
                            time.sleep(0.3)
                            scene_retry = self.adb.screencap()
                            if scene_retry is not None:
                                anchor = self.vision.detect_casino_dialog(scene_retry)
                            if not anchor:
                                self.stop_reason = "Стол закрыт / вылет из игры"
                                self.last_event = "Диалог рулетки закрыт! Сессия остановлена."
                                self._log(f"[ALERT] {self.last_event}")
                                self._emit_status("STOPPED", {"msg": self.last_event, "stop_reason": self.stop_reason})
                                self.is_running = False
                                break
                        pts = self.vision.get_ui_click_points(anchor)

                    elapsed = time.time() - spin_start_t

                    # Outcome check (only after physical minimum spin duration)
                    if elapsed >= self.config.min_spin_duration_sec:
                        outcome, is_win, win_num, debug = self.vision.detect_outcome_multisignal(scene_res, anchor, rec_color)
                        if outcome is not None and is_win is not None:
                            # ----------------------------------------------------
                            # OUTCOME DETECTED!
                            # ----------------------------------------------------
                            self.last_winning_num = win_num if win_num is not None else -1
                            self.spin_index += 1

                            # Process outcome through Official v15.0 FINAL APEX TypeScript Engine
                            engine_res = self.engine.process_outcome(
                                strategy_profile=self.config.strategy_profile,
                                bankroll=self.bankroll,
                                initial_bankroll=self.initial_bankroll,
                                cdt=self.cdt,
                                step=self.current_step,
                                zero_in_sequence=self.zero_in_sequence,
                                current_mode=self.current_mode,
                                previous_mode=self.previous_mode,
                                spins_since_danger_exit=self.spins_since_danger_exit,
                                spins_in_current_mode=self.spins_in_current_mode,
                                sequence_start_mode=self.sequence_start_mode,
                                sequence_target_steps=self.sequence_target_steps,
                                history=self.engine_history,
                                effective_bet=next_bet,
                                recommendation=rec_color,
                                outcome=outcome,
                                session_start_time_ms=int(self.start_time * 1000)
                            )

                            self.is_win = engine_res.get("isWin", engine_res.get("is_win", False))
                            net_profit = engine_res.get("netProfit", engine_res.get("net_profit", 0))
                            self.bankroll = engine_res.get("newBankroll", engine_res.get("new_bankroll", self.bankroll))
                            self.cdt = engine_res.get("nextCdt", engine_res.get("next_cdt", self.cdt))
                            self.current_step = engine_res.get("nextStep", engine_res.get("next_step", self.current_step))
                            self.zero_in_sequence = engine_res.get("nextZeroInSeq", engine_res.get("next_zero_in_seq", self.zero_in_sequence))
                            self.current_mode = engine_res.get("newMode", engine_res.get("new_mode", self.current_mode))
                            self.previous_mode = engine_res.get("newPrevMode", engine_res.get("new_prev_mode", self.previous_mode))
                            self.spins_since_danger_exit = engine_res.get("newSpinsSinceDangerExit", engine_res.get("new_spins_since_danger_exit", self.spins_since_danger_exit))
                            self.spins_in_current_mode = engine_res.get("newSpinsInCurrentMode", engine_res.get("new_spins_in_current_mode", self.spins_in_current_mode))
                            self.sequence_start_mode = engine_res.get("sequenceStartMode", engine_res.get("sequence_start_mode", self.sequence_start_mode))
                            self.sequence_target_steps = engine_res.get("sequenceTargetSteps", engine_res.get("sequence_target_steps", self.sequence_target_steps))
                            self.engine_history = engine_res.get("finalHistory", engine_res.get("final_history", self.engine_history))
                            self.stats = engine_res.get("stats", {})
                            is_terminal_loss = engine_res.get("isTerminalLoss", engine_res.get("is_terminal_loss", False))

                            if is_terminal_loss:
                                self._log(f"\n[СБРОС СЕРИИ] Серия официально завершена (проигрыш крайней ставки {next_bet:,.0f} ₽).")
                                self._log(f"              Долг CDT сброшен на 0 ₽. Запуск новой серии с Шага 1 (базовая ставка).")
                                self.last_event = f"[СБРОС СЕРИИ] Проигрыш {next_bet:,.0f} ₽. Долг списан (CDT=0). Старт с Шага 1."
                                self._emit_status("SERIES_RESET", {
                                    "msg": self.last_event,
                                    "lost_bet": next_bet,
                                    "bankroll": self.bankroll
                                })

                            if self.is_win:
                                self.wins += 1
                                num_str = f"#{win_num} " if win_num >= 0 else ""
                                self.last_event = f"Выпало {num_str}({outcome}) ➔ ВЫИГРЫШ (+{net_profit:,.0f} ₽)"
                            else:
                                self.losses += 1
                                num_str = f"#{win_num} " if win_num >= 0 else ""
                                self.last_event = f"Выпало {num_str}({outcome}) ➔ ПРОИГРЫШ ({net_profit:,.0f} ₽)"

                            self.peak_bankroll = self.stats.get("peakBankroll", self.bankroll)
                            self.max_drawdown = self.stats.get("maxDrawdown", self.max_drawdown)
                            self.history.append(outcome)

                            self._log(f" Результат: {self.last_event}")
                            self._log(f" Баланс: {self.bankroll:,.0f} ₽ (Профит: {self.bankroll - self.initial_bankroll:+,.0f} ₽)")

                            # Log spin
                            self.logger.log_spin(
                                spin_index=self.spin_index,
                                bet_amount=next_bet,
                                bet_color=rec_color,
                                winning_num=win_num,
                                outcome=outcome,
                                is_win=self.is_win,
                                net_profit=net_profit,
                                bankroll=self.bankroll,
                                server_mode=eff_mode,
                                current_step=self.current_step,
                                cdt=self.cdt
                            )

                            self._emit_status("ROUND_FINISHED", {"msg": self.last_event})
                            outcome_detected = True

                            # Check 1: Max-Bet Drain Guard / Emergency Floor
                            if is_terminal_loss or (not self.is_win and next_bet >= 1_000_000):
                                self._log(f"[ВНИМАНИЕ] Зафиксирован проигрыш терминальной ставки серии ({next_bet:,.0f} ₽). Текущий баланс: {self.bankroll:,.0f} ₽.")
                                if self.bankroll < self.config.min_balance_threshold and self.initial_bankroll > self.config.min_balance_threshold:
                                    self.stop_reason = f"Слив серии. Остаток ({self.bankroll:,.0f} ₽) ниже порога {self.config.min_balance_threshold:,.0f} ₽."
                                    self.last_event = f"[ЗАЩИТА БАЛАНСА] Слив серии! Баланс {self.bankroll:,.0f} ₽ < {self.config.min_balance_threshold:,.0f} ₽. Остановка."
                                    self._log(f"\n[ALERT] {self.last_event}")
                                    self._emit_status("BALANCE_GUARD_TRIGGERED", {"msg": self.last_event, "stop_reason": self.stop_reason})
                                    self.is_running = False
                                    break

                            # Check 2: Stop-loss
                            if self.bankroll <= self.initial_bankroll * self.config.stop_loss_pct:
                                self.stop_reason = f"Сработал Stop-Loss (баланс упал ниже {self.config.stop_loss_pct*100:.0f}%)"
                                self.last_event = f"[СТОП-ЛОСС] Баланс исчерпан ({self.bankroll:,.0f} ₽). Игра остановлена."
                                self._log(f"\n[STOP] {self.last_event}")
                                self._emit_status("STOP_LOSS_REACHED", {"msg": self.last_event, "stop_reason": self.stop_reason})
                                self.is_running = False
                                break

                            # Check 3: Take-profit
                            if self.config.take_profit_target and self.bankroll >= self.config.take_profit_target:
                                self.stop_reason = f"Достигнута цель по прибыли ({self.config.take_profit_target:,.0f} ₽)"
                                self.last_event = f"[ЦЕЛЬ ВЗЯТА] Баланс достиг {self.bankroll:,.0f} ₽! Сессия завершена."
                                self._log(f"\n[TARGET] {self.last_event}")
                                self._emit_status("TAKE_PROFIT_REACHED", {"msg": self.last_event, "stop_reason": self.stop_reason})
                                self.is_running = False
                                break

                            # Check 4: User Pause
                            while self.is_paused and self.is_running:
                                self.last_event = "Сессия на паузе (PAUSED)"
                                self._emit_status("PAUSED", {"msg": self.last_event})
                                time.sleep(0.5)
                            if not self.is_running:
                                break

                            # ----------------------------------------------------
                            # PIPELINED IMMEDIATE NEXT BET (Zero Latency)
                            # ----------------------------------------------------
                            calc = self.engine.calculate_bet(
                                strategy_profile=self.config.strategy_profile,
                                bankroll=self.bankroll,
                                cdt=self.cdt,
                                step=self.current_step,
                                current_mode=self.current_mode,
                                sequence_start_mode=self.sequence_start_mode,
                                sequence_target_steps=self.sequence_target_steps,
                                zero_in_sequence=self.zero_in_sequence,
                                history=self.engine_history
                            )
                            self.last_prediction = calc
                            next_bet = self.config.flat_bet_amount if self.config.flat_bet_mode else calc['bet']
                            rec_color = calc['recommendation']
                            eff_mode = calc['effectiveMode']

                            # Check sufficient balance for next bet
                            if self.bankroll < next_bet:
                                self.stop_reason = f"Недостаточно средств для ставки {next_bet:,.0f} ₽ (баланс: {self.bankroll:,.0f} ₽)"
                                self.last_event = f"[БАЛАНС] Не хватает на ставку {next_bet:,.0f} ₽. Игра остановлена."
                                self._log(f"\n[ALERT] {self.last_event}")
                                self._emit_status("INSUFFICIENT_FUNDS", {"msg": self.last_event, "stop_reason": self.stop_reason})
                                self.is_running = False
                                break

                            self.prev_bet_amount = next_bet
                            self.last_event = f"Ставка {next_bet:,.0f} ₽ на {rec_color} (Шаг {self.current_step})"
                            self._log(f"\n--- [СПИН #{self.spin_index + 1}] ---")
                            self._log(f" Режим: {eff_mode} (Сырой: {self.current_mode}) | Шаг: {self.current_step} | CDT: {self.cdt:,.0f} ₽")
                            self._log(f" Действие: {self.last_event}")

                            self._emit_status("PLACING_BET", {
                                "bet": next_bet,
                                "color": rec_color,
                                "step": self.current_step,
                                "mode": eff_mode,
                                "msg": self.last_event
                            })

                            if self.config.post_spin_cooldown_sec > 0:
                                time.sleep(self.config.post_spin_cooldown_sec)

                            # Place bet & click Play immediately
                            self._execute_bet_and_play(pts, rec_color, next_bet)
                            spin_start_t = time.time()

                            self.last_event = f"Вращение колеса... (Ставка {next_bet:,.0f} ₽ на {rec_color})"
                            self._emit_status("SPINNING", {
                                "bet": next_bet,
                                "color": rec_color,
                                "msg": self.last_event
                            })

                            # Round is underway; exit dynamic scan and proceed to quiet sleep
                            break

                    time.sleep(self.config.poll_interval_sec)

                # If watchdog broke out without outcome, recover dialog and bet
                if not outcome_detected and self.is_running:
                    time.sleep(1.0)
                    scene_recover = self.adb.screencap()
                    if scene_recover is not None:
                        anchor = self.vision.detect_casino_dialog(scene_recover)
                        if anchor:
                            pts = self.vision.get_ui_click_points(anchor)
                            # Re-trigger current bet
                            self._execute_bet_and_play(pts, rec_color, next_bet)
                            spin_start_t = time.time()

        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            self.last_event = f"Ошибка: {exc}"
            self.stop_reason = f"Исключение: {exc}"
            self._log(f"\n[КРИТИЧЕСКАЯ ОШИБКА БОТА]:\n{tb}")
            self._emit_status("ERROR", {"msg": self.last_event, "error": tb, "stop_reason": self.stop_reason})
            self.is_running = False

        summary = self.logger.get_summary(self.initial_bankroll, self.bankroll)
        self._log(f"\n==========================================")
        self._log(f" [СЕССИЯ ЗАВЕРШЕНА]")
        self._log(f" Всего спинов: {summary['total_spins']}")
        self._log(f" Винрейт: {summary['win_rate_pct']}% ({summary['wins']} В / {summary['losses']} П)")
        self._log(f" Итоговый баланс: {summary['final_bankroll']:,.0f} ₽")
        self._log(f" Чистая прибыль: {summary['total_profit']:+,.0f} ₽")
        self._log(f" Макс. просадка: {summary['max_drawdown']:,.0f} ₽")
        self._log(f" Логи сохранены: {self.logger.jsonl_path}")
        self._log(f"==========================================\n")
        self._emit_status("STOPPED", {"summary": summary, "msg": self.last_event, "stop_reason": self.stop_reason})

    def stop(self):
        """Signals the bot to stop cleanly after current spin."""
        self.is_running = False
        self.last_event = "Остановка по запросу пользователя..."
        if hasattr(self, 'engine') and self.engine:
            self.engine.close()
