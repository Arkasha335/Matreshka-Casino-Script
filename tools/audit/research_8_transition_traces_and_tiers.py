import math

def print_ladder(title, b0, target_steps, bankroll=3_500_000, shape='GEOM', switch_schedule=None):
    """
    Prints exact step-by-step progression table.
    switch_schedule: dict mapping step -> (new_mode_name, new_b0, new_target_steps, new_shape)
    """
    print(f"\n=== {title} (Init Wallet={bankroll:,} RUB) ===")
    print(f"{'Step':>4} | {'Mode':<10} | {'N':>2} | {'Bet (RUB)':>10} | {'Mult X':>7} | {'CDT Before':>10} | {'Total Risk':>10} | {'Net if Win':>11} | {'Note'}")
    print("-" * 100)

    cdt = 0
    prev_b = None
    cur_mode, cur_b0, cur_n, cur_sh = 'START', b0, target_steps, shape

    for step in range(1, 12):
        if switch_schedule and step in switch_schedule:
            cur_mode, cur_b0, cur_n, cur_sh = switch_schedule[step]

        cycle_cap = bankroll
        terminal_cap = max(1000, min(1_000_000, math.floor(cycle_cap / 1.90)))
        rem = max(1, cur_n - step + 1)
        min_tbb = math.ceil((cdt + cur_b0) / 0.98)

        if step == 1:
            bet = min(cur_b0, bankroll)
            note = f"Base B0={cur_b0}"
        elif rem == 1:
            bet = min(min_tbb, terminal_cap, bankroll - cdt)
            note = "TERMINAL"
        else:
            if cur_sh == 'FLAT_TBB':
                bet = min_tbb
                note = f"Flat TBB (+{cur_b0})"
            else:
                pb = prev_b if prev_b else cur_b0
                dx = max(2.025, min(2.40, (terminal_cap / pb) ** (1.0 / rem)))
                geom = math.floor(pb * dx + 0.5)
                bet = max(min_tbb, geom)
                note = f"Geom dx={dx:.3f}"
            if rem == 2 and terminal_cap >= 900_000:
                max_pen = math.floor(terminal_cap * 0.98) - cdt - 100
                if max_pen >= math.ceil((cdt + 100) / 0.98):
                    if max_pen < bet:
                        note += " [980k Guard]"
                    bet = min(bet, max_pen)

        bet = min(bet, 1_000_000, max(0, bankroll - cdt))
        if bet < 1000:
            print(f"{step:>4} | OUT OF FUNDS (remaining={bankroll-cdt:,})")
            break

        mult_str = f"{bet / prev_b:.3f}x" if prev_b else "  1.000x"
        total_risk = cdt + bet
        net_win = round(bet * 0.98) - cdt
        if net_win <= 0:
            note += " !!DEAD!!"

        print(f"{step:>4} | {cur_mode:<10} | {cur_n:>2} | {bet:>10,d} | {mult_str:>7} | {cdt:>10,d} | {total_risk:>10,d} | {net_win:>+11,d} | {note}")
        cdt += bet
        prev_b = bet
        if rem == 1 or cdt >= bankroll:
            break

# Case 1: Pure ZEBRA (N=9, B0=3000) vs Switching to DANGER at Step 4 (GEOM vs FLAT_TBB)
print_ladder("1. PURE ZEBRA (B0=3000, N=9, GEOM)", 3000, 9, shape='GEOM')
print_ladder("2. ZEBRA(3000/N9) -> TRANSITION(1500/N10) at St3 -> DANGER(1000/N10) at St5 [GEOM]", 3000, 9, shape='GEOM',
             switch_schedule={1: ('ZEBRA',3000,9,'GEOM'), 3: ('TRANSITION',1500,10,'GEOM'), 5: ('DANGER',1000,10,'GEOM')})
print_ladder("3. ZEBRA(3000/N9) -> TRANSITION(1500/N10) at St3 -> DANGER(1000/N10) at St5 [FLAT_TBB]", 3000, 9, shape='GEOM',
             switch_schedule={1: ('ZEBRA',3000,9,'GEOM'), 3: ('TRANSITION',1500,10,'FLAT_TBB'), 5: ('DANGER',1000,10,'FLAT_TBB')})
print_ladder("4. TRANSITION(1500/N10) -> DANGER(1000/N10) at St4 [GEOM vs FLAT_TBB]", 1500, 10, shape='GEOM',
             switch_schedule={1: ('TRANSITION',1500,10,'GEOM'), 4: ('DANGER',1000,10,'FLAT_TBB')})
print_ladder("5. PURE DANGER (B0=1000, N=10, GEOM)", 1000, 10, shape='GEOM',
             switch_schedule={1: ('DANGER',1000,10,'GEOM')})
print_ladder("6. Low Bankroll 1,000,000 RUB (B0=1000, N=9)", 1000, 9, bankroll=1_000_000, shape='GEOM',
             switch_schedule={1: ('ALL',1000,9,'GEOM')})
