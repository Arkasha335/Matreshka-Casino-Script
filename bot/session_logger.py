"""
Session Logger module for Matreshka RP Casino.
Saves spin-by-spin telemetry to JSONL and CSV for complete auditability.
"""

import os
import json
import csv
import time
from typing import Dict, Any, List, Optional
from .config import Outcome, ServerMode

class SessionLogger:
    def __init__(self, logs_dir: str, session_id: Optional[str] = None):
        self.logs_dir = logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)
        self.session_id = session_id or time.strftime("session_%Y%m%d_%H%M%S")
        self.jsonl_path = os.path.join(self.logs_dir, f"{self.session_id}.jsonl")
        self.csv_path = os.path.join(self.logs_dir, f"{self.session_id}.csv")
        self.start_time = time.time()
        self.entries: List[Dict[str, Any]] = []

        # Initialize CSV header if not exists
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "spin", "time", "bet_amount", "bet_color", "winning_num",
                    "outcome", "is_win", "net_profit", "bankroll", "mode",
                    "step", "cdt"
                ])

    def log_spin(
        self,
        spin_index: int,
        bet_amount: int,
        bet_color: Outcome,
        winning_num: int,
        outcome: Outcome,
        is_win: bool,
        net_profit: int,
        bankroll: int,
        server_mode: ServerMode,
        current_step: int,
        cdt: int
    ) -> Dict[str, Any]:
        """Records a single spin outcome and flushes to disk immediately."""
        entry = {
            "timestamp": int(time.time() * 1000),
            "spin": spin_index,
            "bet_amount": bet_amount,
            "bet_color": bet_color,
            "winning_num": winning_num,
            "outcome": outcome,
            "is_win": is_win,
            "net_profit": net_profit,
            "bankroll": bankroll,
            "mode": server_mode,
            "step": current_step,
            "cdt": cdt
        }
        self.entries.append(entry)

        # Append to JSONL
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Append to CSV
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                spin_index,
                time.strftime("%H:%M:%S"),
                bet_amount,
                bet_color,
                winning_num,
                outcome,
                "WIN" if is_win else "LOSS",
                net_profit,
                bankroll,
                server_mode,
                current_step,
                cdt
            ])

        return entry

    def get_summary(self, initial_bankroll: int, current_bankroll: int) -> Dict[str, Any]:
        """Calculates final session summary stats."""
        total_spins = len(self.entries)
        wins = sum(1 for e in self.entries if e["is_win"])
        win_rate = (wins / total_spins * 100) if total_spins > 0 else 0.0
        total_profit = current_bankroll - initial_bankroll
        duration_sec = time.time() - self.start_time

        peak = initial_bankroll
        max_dd = 0
        running_bank = initial_bankroll
        for e in self.entries:
            running_bank += e["net_profit"]
            if running_bank > peak:
                peak = running_bank
            dd = peak - running_bank
            if dd > max_dd:
                max_dd = dd

        return {
            "session_id": self.session_id,
            "duration_sec": round(duration_sec, 1),
            "total_spins": total_spins,
            "wins": wins,
            "losses": total_spins - wins,
            "win_rate_pct": round(win_rate, 2),
            "initial_bankroll": initial_bankroll,
            "final_bankroll": current_bankroll,
            "total_profit": total_profit,
            "max_drawdown": max_dd,
            "peak_bankroll": peak
        }
