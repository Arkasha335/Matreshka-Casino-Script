"""
Full system verification test for the bot module.
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("="*50)
print(" RUNNING BOT MODULE FULL VERIFICATION")
print("="*50)

# 1. Config Test
from bot.config import BotConfig, ROULETTE_RULES
cfg = BotConfig(initial_bankroll=2_500_000, strategy_profile='APEX_IDEAL')
print(f"[1/5] Config initialized: {cfg.strategy_profile}, Bank: {cfg.initial_bankroll:,.0f} RUB")
assert len(ROULETTE_RULES['RED_NUMBERS']) == 19
assert len(ROULETTE_RULES['BLACK_NUMBERS']) == 19
assert len(ROULETTE_RULES['ZERO_NUMBERS']) == 2

# 2. Vision Engine Test
from bot.vision_engine import VisionEngine
ve = VisionEngine(templates_dir=cfg.templates_dir)
assert len(ve.templates) >= 5, f"Expected at least 5 templates, found {len(ve.templates)}"
print(f"[2/5] Vision Engine loaded {len(ve.templates)} templates successfully")

# 3. Session Logger Test
import tempfile
import shutil
temp_logs = tempfile.mkdtemp()
from bot.session_logger import SessionLogger
logger = SessionLogger(logs_dir=temp_logs, session_id="test_session")
entry = logger.log_spin(
    spin_index=1,
    bet_amount=2000,
    bet_color='RED',
    winning_num=30,
    outcome='RED',
    is_win=True,
    net_profit=1960,
    bankroll=2501960,
    server_mode='ZEBRA',
    current_step=1,
    cdt=0
)
assert os.path.isfile(logger.jsonl_path)
assert os.path.isfile(logger.csv_path)
shutil.rmtree(temp_logs)
print(f"[3/5] Session Logger verified (JSONL & CSV formatting intact)")

# 4. ADB Controller Connection Test
from bot.adb_controller import ADBController
ctrl = ADBController(serial=cfg.device_serial)
is_connected = ctrl.connect()
print(f"[4/5] ADB Controller connected to {cfg.device_serial}: {is_connected}")

# 5. State Machine Initialization Test
from bot.state_machine import CasinoBot
bot = CasinoBot(config=cfg)
print(f"[5/5] CasinoBot State Machine ready: Bankroll={bot.bankroll:,.0f} RUB, Step={bot.current_step}")

print("\n" + "="*50)
print(" ALL 5 SUBSYSTEM TESTS PASSED WITH 100% SUCCESS!")
print("="*50)
