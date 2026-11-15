"""
Master Unified Entry Point for Matreshka RP Casino Bot (v15.0 APEX FINAL).
All-in-One: Interactive Dashboard, Farm Launcher, and Auto-Calibrator.

Usage:
    python run.py             # Launches interactive Master Dashboard
    python run.py --calibrate # Launches interactive coordinate calibrator
    python run.py --test      # Runs 1 test spin (1000 RUB fixed)
"""

import sys
import os

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.dashboard import MasterDashboard
from bot.calibrate import CasinoCalibrator, run_interactive_menu

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--calibrate" in args or "-c" in args:
        run_interactive_menu()
    elif "--test" in args or "-t" in args:
        cal = CasinoCalibrator()
        _, pts = cal.capture_and_annotate()
        if pts:
            cal.test_full_spin(pts, 1000, 'RED')
    else:
        app = MasterDashboard()
        app.run()
