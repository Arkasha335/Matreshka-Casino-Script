from simulate_terminal_strategies import MPDPredictor, sessions

def strat_apex_golden(step, cdt, bank, init_bank):
    # Calibrated Golden Apex 10-step ladder
    b0 = 1600
    if cdt <= 0: return b0
    tbb = round((cdt + b0) / 0.98)
    if step == 2: return round(tbb * 1.12)
    if step == 3: return round(tbb * 1.06)
    if step >= 10: return min(1_000_000, bank)
    return min(1_000_000, tbb)

total_net = 0
sessions_won = 0
max_step = 0
limit_hits = 0

for idx, sess in enumerate(sessions):
    pred = MPDPredictor()
    bank = 3_806_838
    cdt = 0
    step = 1
    sess_max = 0
    for out in sess['outcomes']:
        rec = pred.get_recommendation()
        bet = strat_apex_golden(step, cdt, bank, 3_806_838)
        if bet > 1_000_000:
            limit_hits += 1
            bet = 1_000_000
        sess_max = max(sess_max, step)
        if out == rec:
            bank += bet * 0.98
            cdt = 0
            step = 1
        else:
            bank -= bet
            cdt += bet
            step += 1
        pred.add_result(out)
    prof = bank - 3_806_838
    total_net += prof
    max_step = max(max_step, sess_max)
    if prof > 0: sessions_won += 1
    print(f"Session {idx+1:2d} ({sess['name'][:30]:30s}): Profit = {prof:10.2f} RUB | Max Step = {sess_max}")

print(f"\nTOTAL NET PROFIT: {total_net:,.2f} RUB")
print(f"SESSIONS WON:     {sessions_won} / {len(sessions)} ({sessions_won/len(sessions)*100:.1f}%)")
print(f"MAX STEP:         {max_step}")
print(f"LIMIT HITS:       {limit_hits}")
