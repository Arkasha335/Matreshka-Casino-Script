import random, math, statistics
from engine_mirror import js_round

GAME_RULES = {
    'TOTAL_SLOTS': 50,
    'RED_SLOTS': 24,
    'BLACK_SLOTS': 24,
    'ZERO_SLOTS': 2,
    'TAX_RATE': 0.02,
}

def generate_markov_spins(n_spins=10_000, p_alt=0.55, p_zero=0.04):
    spins = []
    curr = 'RED'
    for _ in range(n_spins):
        if random.random() < p_zero:
            spins.append('ZERO')
        else:
            if random.random() < p_alt:
                curr = 'BLACK' if curr == 'RED' else 'RED'
            spins.append(curr)
    return spins

def test_engine_on_stream(spins, window=15):
    hist = []
    wins = 0
    nz_spins = 0
    cur_ls = 0
    max_ls = 0
    ls_list = []
    
    for o in spins:
        if not hist:
            pred = 'RED'
        else:
            nz = [h for h in hist if h != 'ZERO']
            if len(nz) < 2:
                pred = nz[-1] if nz else 'RED'
            else:
                win_nz = nz[-window:]
                tot = len(win_nz)
                rc = win_nz.count('RED')
                bc = win_nz.count('BLACK')
                r_r = rc / tot
                b_r = bc / tot
                alpha = 'RED' if r_r > 0.55 else ('BLACK' if b_r > 0.55 else 'NEUTRAL')
                omega = 'BLACK' if alpha == 'RED' else ('RED' if alpha == 'BLACK' else 'NEUTRAL')
                top_r = max(r_r, b_r)
                cas = 0
                cac = nz[-1]
                for h in reversed(nz):
                    if h == cac: cas += 1
                    else: break
                
                # 4-spin patterns
                pred = None
                if len(nz) >= 4:
                    L1, L2, L3, L4 = nz[-1], nz[-2], nz[-3], nz[-4]
                    if L1 == L3 and L2 == L4 and L1 != L2:
                        pred = 'BLACK' if L1 == 'RED' else 'RED'
                    elif L1 == L2 == L3 and L4 != L1:
                        pred = 'BLACK' if L1 == 'RED' else 'RED'
                
                if pred is None:
                    L1, L2 = nz[-1], nz[-2]
                    if cas >= 3:
                        pred = 'BLACK' if cac == 'RED' else 'RED'
                    elif L1 == L2:
                        if L1 == alpha and top_r >= 0.70:
                            pred = 'BLACK' if L1 == 'RED' else 'RED'
                        else:
                            pred = L1
                    else:
                        # alternation
                        non_zero_6 = nz[-6:]
                        if len(non_zero_6) >= 4:
                            alts = sum(1 for i in range(1, len(non_zero_6)) if non_zero_6[i] != non_zero_6[i-1])
                            arate = alts / (len(non_zero_6) - 1)
                            followL1 = False if arate >= 0.80 else True
                        else:
                            followL1 = True
                        pred = L1 if followL1 else ('BLACK' if L1 == 'RED' else 'RED')
                        if L1 == alpha and L2 == omega:
                            osb = 0
                            for i in range(len(nz)-2, -1, -1):
                                if nz[i] == omega: osb += 1
                                else: break
                            if osb >= 2:
                                pred = alpha

        if o != 'ZERO':
            nz_spins += 1
            if pred == o:
                wins += 1
                ls_list.append(cur_ls)
                cur_ls = 0
            else:
                cur_ls += 1
                if cur_ls > max_ls: max_ls = cur_ls
        else:
            cur_ls += 1
            if cur_ls > max_ls: max_ls = cur_ls
        hist.append(o)
        
    return {
        'nz_winrate': wins / nz_spins if nz_spins else 0,
        'max_loss_streak': max_ls,
        'avg_loss_streak': sum(ls_list) / len(ls_list) if ls_list else 0,
    }

if __name__ == '__main__':
    random.seed(42)
    print('=== MONTE CARLO STRESS TEST: 100,000 SPINS (10 x 10,000) ===\n')
    
    for p_alt in [0.50, 0.55, 0.60]:
        print(f'--- Simulation with Alternation Bias p_alt = {p_alt:.2f} ---')
        w15_wr, w24_wr = [], []
        w15_mls, w24_mls = [], []
        
        for run in range(10):
            spins = generate_markov_spins(10_000, p_alt=p_alt)
            r15 = test_engine_on_stream(spins, window=15)
            r24 = test_engine_on_stream(spins, window=24)
            w15_wr.append(r15['nz_winrate'])
            w24_wr.append(r24['nz_winrate'])
            w15_mls.append(r15['max_loss_streak'])
            w24_mls.append(r24['max_loss_streak'])
            
        print(f"W=15 (v14.0): Avg NZ WR = {statistics.mean(w15_wr):.2%} | Peak Loss Streak = {max(w15_mls)} (avg {statistics.mean(w15_mls):.1f})")
        print(f"W=24 (v15.0): Avg NZ WR = {statistics.mean(w24_wr):.2%} | Peak Loss Streak = {max(w24_mls)} (avg {statistics.mean(w24_mls):.1f})")
        print()
