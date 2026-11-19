"""
Benchmark candidate architectures for v16.1 APEX-Neural vs v16.0 and v15.2
Evaluates:
1. Win Rate (All 49 sessions, Bot logs, Fresh log)
2. Max Step Reached across all sessions (Deep Step Risk)
3. Step >= 6 occurrence count
4. Total PnL (RUB) under standard bankroll execution
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()
print(f"Loaded {len(sessions)} unique sessions.")

# Let's inspect task-958 status or results
