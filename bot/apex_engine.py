"""
Official v15.0 FINAL APEX Math & Staking Engine Client.
Provides 100.000% mathematical parity with the Next.js TypeScript web application.
Communicates directly with the compiled lib/engine bundle via persistent Node worker.
"""

import os
import sys
import json
import time
import subprocess
from typing import Dict, Any, List, Optional, Tuple

class ApexEngineClient:
    def __init__(self):
        self.worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine_worker.js")
        self.proc: Optional[subprocess.Popen] = None
        self._ensure_worker()

    def _ensure_worker(self):
        if self.proc is None or self.proc.poll() is not None:
            self.proc = subprocess.Popen(
                ["node", self.worker_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1
            )
            # Health check ping
            self._send({"cmd": "ping"})

    def _send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sends JSON request to worker and reads single JSON line response."""
        for attempt in range(2):
            try:
                self._ensure_worker()
                line = json.dumps(payload) + "\n"
                self.proc.stdin.write(line)
                self.proc.stdin.flush()
                resp_line = self.proc.stdout.readline()
                if not resp_line:
                    raise IOError("Worker stdout closed unexpectedly")
                data = json.loads(resp_line.strip())
                if "error" in data:
                    raise RuntimeError(f"Engine worker error: {data['error']}")
                return data
            except Exception as exc:
                if attempt == 1:
                    raise
                if self.proc:
                    try:
                        self.proc.terminate()
                    except Exception:
                        pass
                self.proc = None

    def calculate_bet(
        self,
        strategy_profile: str,
        bankroll: int,
        cdt: int,
        step: int,
        current_mode: str,
        sequence_start_mode: str,
        sequence_target_steps: Optional[int],
        zero_in_sequence: int,
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculates exact next bet and recommendation via v15.0 FINAL APEX.
        Returns: {
            'bet': int,
            'recommendation': 'RED' | 'BLACK',
            'confidence': int,
            'state': str,
            'effectiveMode': str,
            'isZeroShock': bool,
            'isZebraLocked': bool,
            'engineParams': dict
        }
        """
        payload = {
            "cmd": "calc_bet",
            "profile": strategy_profile,
            "bankroll": bankroll,
            "cdt": cdt,
            "step": step,
            "currentMode": current_mode,
            "sequenceStartMode": sequence_start_mode,
            "sequenceTargetSteps": sequence_target_steps,
            "zeroInSequence": zero_in_sequence,
            "history": history
        }
        return self._send(payload)

    def process_outcome(
        self,
        strategy_profile: str,
        bankroll: int,
        initial_bankroll: int,
        cdt: int,
        step: int,
        zero_in_sequence: int,
        current_mode: str,
        previous_mode: str,
        spins_since_danger_exit: int,
        spins_in_current_mode: int,
        sequence_start_mode: str,
        sequence_target_steps: Optional[int],
        history: List[Dict[str, Any]],
        effective_bet: int,
        recommendation: str,
        outcome: str,
        session_start_time_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Applies game rules, 2% commission rounding, debt tracking, mode transitions,
        and full detailed RiskGuard KPI analytics.
        """
        payload = {
            "cmd": "process_outcome",
            "profile": strategy_profile,
            "bankroll": bankroll,
            "initialBankroll": initial_bankroll,
            "cdt": cdt,
            "step": step,
            "zeroInSequence": zero_in_sequence,
            "currentMode": current_mode,
            "previousMode": previous_mode,
            "spinsSinceDangerExit": spins_since_danger_exit,
            "spinsInCurrentMode": spins_in_current_mode,
            "sequenceStartMode": sequence_start_mode,
            "sequenceTargetSteps": sequence_target_steps,
            "history": history,
            "effectiveBet": effective_bet,
            "recommendation": recommendation,
            "outcome": outcome,
            "sessionStartTime": session_start_time_ms or int(time.time() * 1000)
        }
        return self._send(payload)

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None
