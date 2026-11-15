"""
Configuration module for the Matreshka RP Casino Automation Bot.
Defines parameters, timeouts, strategy profiles, and farm settings.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
import os

StrategyProfile = Literal['APEX_IDEAL', 'TURBO_HARVEST', 'SHIELD_CONSERVATIVE']
Outcome = Literal['RED', 'BLACK', 'ZERO']
ServerMode = Literal['ZEBRA', 'TRANSITION', 'DANGER']

# 40-slot table rules (Matreshka RP Roulette: 0..39)
# Slots: 0 and 39 are green (ZERO)
# Red slots: 19 numbers
# Black slots: 19 numbers
ROULETTE_RULES = {
    'TOTAL_SLOTS': 40,
    'RED_SLOTS': 19,
    'BLACK_SLOTS': 19,
    'ZERO_SLOTS': 2,
    'MIN_BET': 1000,
    'MAX_BET': 1000000,
    'TAX_RATE': 0.02, # 2% commission on net win
    'WIN_NET_RATIO': 0.98,
    'RED_NUMBERS': [2, 3, 5, 8, 9, 10, 12, 14, 16, 21, 23, 25, 28, 29, 30, 32, 33, 35, 37],
    'BLACK_NUMBERS': [1, 4, 6, 7, 11, 13, 15, 17, 18, 19, 20, 22, 24, 26, 27, 31, 34, 36, 38],
    'ZERO_NUMBERS': [0, 39],
}

@dataclass
class BotConfig:
    # ADB & Device settings
    device_serial: str = "127.0.0.1:16384"
    adb_path: Optional[str] = None # Auto-detected if None
    
    # Financial settings
    initial_bankroll: int = 1_000_000
    strategy_profile: StrategyProfile = 'APEX_IDEAL'
    stop_loss_pct: float = 0.50 # Stop if current bankroll drops below 50% of initial
    min_balance_threshold: int = 2_000_000 # Emergency floor: hard stop if bankroll falls below 2,000,000 ₽
    take_profit_target: Optional[int] = None # e.g. 5_000_000
    flat_bet_mode: bool = False # If True: sets ALL bets to fixed flat_bet_amount (Beta Test mode)
    flat_bet_amount: int = 1000 # Minimum fixed bet for zero-risk test
    
    # Performance & Speed (Dynamic scanning: max speed & 100% lag-resilient)
    fast_mode: bool = True # Mechanical fast betting (minimal delay)
    spin_sleep_sec: float = 4.8 # Initial quiet sleep while wheel spins (0% CPU)
    min_spin_duration_sec: float = 5.2 # Minimum physical spin duration to avoid reading flickering cells
    poll_interval_sec: float = 0.12 # Dynamic scan rate (~8 times/sec for instant reaction)
    post_spin_cooldown_sec: float = 0.35 # Minimal delay after outcome before placing next bet
    watchdog_timeout_sec: float = 40.0 # Timeout for round completion
    
    # Paths
    project_root: str = field(default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    templates_dir: str = field(default_factory=lambda: os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
    logs_dir: str = field(default_factory=lambda: os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"))

    def __post_init__(self):
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
