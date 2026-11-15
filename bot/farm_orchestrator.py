"""
Farm Orchestrator module for Matreshka RP Casino.
Manages multiple concurrent MuMu Player instances for multi-account AFK farming.
"""

import sys
import os
import time
import threading
from typing import Dict, List, Optional

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from bot.config import BotConfig, StrategyProfile
from bot.state_machine import CasinoBot
from bot.adb_controller import ADBController

class AccountWorker:
    def __init__(self, port: int, initial_bankroll: int, profile: StrategyProfile = 'APEX_IDEAL'):
        self.port = port
        self.serial = f"127.0.0.1:{port}"
        self.config = BotConfig(
            device_serial=self.serial,
            initial_bankroll=initial_bankroll,
            strategy_profile=profile
        )
        self.last_status: Dict = {"state": "IDLE", "bankroll": initial_bankroll, "profit": 0, "spin": 0}
        self.bot = CasinoBot(self.config, on_status_update=self._on_update)
        self.thread: Optional[threading.Thread] = None

    def _on_update(self, status: Dict):
        self.last_status.update(status)

    def start(self):
        self.thread = threading.Thread(target=self.bot.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.bot.stop()

class FarmOrchestrator:
    def __init__(self):
        self.workers: Dict[int, AccountWorker] = {}

    @staticmethod
    def scan_mumu_ports(start_port: int = 16384, max_instances: int = 10) -> List[int]:
        """
        Discovers active MuMu Player 12 instance ports.
        Base port is 16384, step is 32 (16384, 16416, 16448, 16480...).
        """
        active_ports = []
        adb_path = ADBController.find_adb()
        if not adb_path:
            return active_ports

        for i in range(max_instances):
            port = start_port + i * 32
            ctrl = ADBController(serial=f"127.0.0.1:{port}", adb_path=adb_path)
            if ctrl.connect():
                active_ports.append(port)
        return active_ports

    def add_worker(self, port: int, initial_bankroll: int, profile: StrategyProfile = 'APEX_IDEAL'):
        worker = AccountWorker(port, initial_bankroll, profile)
        self.workers[port] = worker

    def start_all(self):
        for port, worker in self.workers.items():
            print(f"[FARM] Starting Worker for {worker.serial}...")
            worker.start()

    def stop_all(self):
        for port, worker in self.workers.items():
            print(f"[FARM] Stopping Worker for {worker.serial}...")
            worker.stop()

    def print_farm_dashboard(self):
        """Prints live ASCII telemetry for all farm accounts."""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("="*65)
        print("        MATRESHKA RP CASINO - MULTI-ACCOUNT FARM")
        print("="*65)
        print(f"{'PORT':<8} {'STATE':<15} {'SPINS':<8} {'BANKROLL':<14} {'PROFIT':<14}")
        print("-" * 65)

        total_profit = 0
        total_spins = 0
        for port, w in self.workers.items():
            st = w.last_status
            state = st.get('state', 'UNKNOWN')
            spins = st.get('spin', 0)
            bank = st.get('bankroll', w.config.initial_bankroll)
            profit = st.get('profit', 0)

            total_profit += profit
            total_spins += spins

            profit_str = f"{profit:+,.0f} ₽"
            print(f"{port:<8} {state:<15} {spins:<8} {bank:,.0f} ₽     {profit_str:<14}")

        print("-" * 65)
        print(f" TOTAL ACCOUNTS: {len(self.workers)} | TOTAL SPINS: {total_spins} | NET FARM PROFIT: {total_profit:+,.0f} ₽")
        print("="*65)

if __name__ == "__main__":
    orchestrator = FarmOrchestrator()
    ports = orchestrator.scan_mumu_ports()
    print(f"Discovered active MuMu ports: {ports}")
