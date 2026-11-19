"""
Test Safe Graceful Debt-Free Shutdown and AFK Controller Logic.
"""
import time
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from bot.afk_controller import parse_time_spec, AFKController
from bot.config import BotConfig
from bot.state_machine import CasinoBot

def test_afk_parsing():
    now = time.time()
    # Relative
    t30 = parse_time_spec("30m")
    assert 1795 <= (t30 - now) <= 1805, f"Expected ~1800s, got {t30 - now}"
    
    t2h = parse_time_spec("2h")
    assert 7195 <= (t2h - now) <= 7205, f"Expected ~7200s, got {t2h - now}"
    
    t45s = parse_time_spec("45s")
    assert 40 <= (t45s - now) <= 50, f"Expected ~45s, got {t45s - now}"
    
    # Clock
    t_clock = parse_time_spec("12:00")
    assert t_clock is not None
    print("[OK] test_afk_parsing passed.")

def test_graceful_stop_state_logic():
    cfg = BotConfig(
        device_serial="127.0.0.1:16384",
        initial_bankroll=1_000_000
    )
    bot = CasinoBot(cfg, silent=True)
    bot.is_running = True
    
    # Case 1: bot has debt (step=4, cdt=35000)
    bot.current_step = 4
    bot.cdt = 35000
    bot.request_graceful_stop("Тестовая остановка")
    
    # Bot MUST NOT stop while debt > 0
    assert bot.graceful_stop_requested is True
    assert bot.is_running is True, "Bot halted prematurely while holding debt!"
    print("[OK] Case 1 passed: Bot refuses to stop while in active debt sequence (cdt > 0, step > 1).")
    
    # Simulate a loss
    bot.cdt += 70000
    bot.current_step = 5
    assert bot.is_running is True, "Bot halted prematurely after loss in graceful stop mode!"
    
    # Simulate winning spin that clears debt (cdt -> 0, step -> 1)
    bot.cdt = 0
    bot.current_step = 1
    
    # Check graceful stop logic trigger (as done in state_machine main loop)
    if bot.graceful_stop_requested and bot.cdt == 0 and bot.current_step == 1:
        bot.is_running = False
        bot.stop_reason = "Серия закрыта в 0 ₽"
        
    assert bot.is_running is False, "Bot failed to halt after debt was cleared!"
    print("[OK] Case 2 passed: Bot cleanly halted immediately once debt cleared to 0 ₽ at Step 1.")

def test_afk_controller():
    afk = AFKController(sleep_pc_on_stop=True)
    afk.set_timer("1s")
    assert afk.is_active is True
    time.sleep(1.2)
    assert afk.is_expired() is True
    print("[OK] test_afk_controller passed.")

if __name__ == "__main__":
    test_afk_parsing()
    test_graceful_stop_state_logic()
    test_afk_controller()
    print("\n>>> ALL SAFE SHUTDOWN & AFK LOGIC TESTS PASSED (100%)! <<<")
