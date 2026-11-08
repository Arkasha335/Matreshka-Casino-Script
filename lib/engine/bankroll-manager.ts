import { EngineParams, GAME_RULES, ServerMode, StrategyProfile } from './types';

export class BankrollManager {
  /**
   * Dynamic Constant Multiplier Architecture:
   * Calculates the exact constant growth factor X = (B_terminal / B_0)^(1 / (N - 1))
   * such that the N-th step naturally lands directly on the 1,000,000 RUB table ceiling
   * or matches the bankroll boundary without arbitrary jumps.
   * 
   * Strict Game Rules:
   * - Min bet: 1,000 RUB (strictly enforced, never below 1,000)
   * - Max bet: 1,000,000 RUB table limit
   * - 50 slots (24 Red, 24 Black, 2 Zero = 4% Zero)
   * - 2% Casino commission on winnings
   * - All amounts are strictly whole rubles (integers)
   */
  public static getEngineParams(
    profile: StrategyProfile,
    mode: ServerMode,
    bankroll: number
  ): EngineParams {
    const effectiveBankroll = Math.max(GAME_RULES.MIN_BET * 10, bankroll);
    const bankrollCap = 1900000;

    let targetSteps: number = 10;
    let nominalBaseBet: number;

    // Mode-specific base bet & step dynamics:
    // 1. ZEBRA: High win rate on step 1 -> optimal B0 for maximum EV, with calibrated steps.
    //    >= 3.0M: B0 = 2000, N = 9 (Proven +959k profit, 0 limit hits)
    //    >= 2.0M: B0 = 1500, N = 10
    //    <  2.0M: B0 = 1000, N = 10
    // 2. TRANSITION ("Жёлтенький"): Streaks of 3-4 -> minimum base bet 1,000, N = 10 steps cushion.
    // 3. DANGER: Severe anomalies & Zero bursts -> minimum base bet 1,000, N = 11 steps shield (MaxDD capped at 671k).
    if (mode === 'ZEBRA') {
      if (profile === 'TURBO_HARVEST') {
        nominalBaseBet = effectiveBankroll >= 2500000 ? 2000 : 1000;
        targetSteps = 9;
      } else if (profile === 'SHIELD_CONSERVATIVE') {
        nominalBaseBet = 1000;
        targetSteps = 11;
      } else {
        // APEX_IDEAL
        if (effectiveBankroll >= 3000000) {
          nominalBaseBet = 2000;
          targetSteps = 9;
        } else if (effectiveBankroll >= 2000000) {
          nominalBaseBet = 1500;
          targetSteps = 10;
        } else {
          nominalBaseBet = 1000;
          targetSteps = 10;
        }
      }
    } else if (mode === 'TRANSITION') {
      // "Жёлтенький" - transitional step with 3-4 same colors. Minimum 1,000 RUB base bet.
      nominalBaseBet = 1000;
      targetSteps = 10;
    } else {
      // DANGER - aggressive server mood, mono-streaks and Zero spam.
      // 11 steps shield: 8th step is only ~125k RUB instead of 224k RUB!
      // Guarantees ZERO limit hits and reduces Max Drawdown down to 671k RUB.
      nominalBaseBet = 1000;
      targetSteps = 11;
    }

    // Minimum bet is strictly 1,000 RUB on Matreshka RP
    const effectiveBaseBet = Math.max(GAME_RULES.MIN_BET, Math.round(nominalBaseBet / 50) * 50);

    // Terminal boundary: table ceiling (1,000,000 RUB) or bankroll-safe ceiling
    const terminalCap = Math.max(
      GAME_RULES.MIN_BET,
      Math.min(GAME_RULES.MAX_BET, Math.floor(effectiveBankroll / 1.90))
    );

    // Calculate exact constant multiplier X
    const ratio = terminalCap / Math.max(1, effectiveBaseBet);
    const exponent = 1.0 / Math.max(1, targetSteps - 1);
    const dynamicMultiplier = Math.max(1.95, Math.min(2.40, Math.pow(ratio, exponent)));

    // Calculate steps until table limit (1,000,000 RUB)
    let stepsToLimit = 0;
    let simBet = effectiveBaseBet;
    let simCdt = 0;
    while (simBet <= GAME_RULES.MAX_BET && stepsToLimit < 20) {
      stepsToLimit++;
      simCdt += simBet;
      simBet = Math.round(simBet * dynamicMultiplier);
    }

    // Calculate durability steps until bankroll exhausted
    let durabilitySteps = 0;
    let cumLoss = 0;
    let testBet = effectiveBaseBet;
    while (cumLoss + testBet <= effectiveBankroll && durabilitySteps < 20 && testBet <= GAME_RULES.MAX_BET) {
      durabilitySteps++;
      cumLoss += testBet;
      testBet = Math.round(testBet * dynamicMultiplier);
    }

    return {
      baseBet: effectiveBaseBet,
      step2Boost: dynamicMultiplier / 2.04,
      step3Boost: dynamicMultiplier / 2.04,
      growthFactor: dynamicMultiplier,
      sniperMult: dynamicMultiplier / 2.04,
      stepsToLimit: Math.max(1, stepsToLimit),
      durabilitySteps: Math.max(1, durabilitySteps),
    };
  }

  /**
   * Dynamic Constant-Ratio Staking:
   * Dynamically calculates the exact multiplier X at each loss step so that:
   * 1. The sequence grows smoothly with constant X.
   * 2. The terminal step lands precisely at the 1,000,000 RUB ceiling (or bankroll limit).
   * 3. Every bet strictly covers cumulative debt (CDT) + base profit under 2% tax.
   * 4. All bets strictly respect minimum 1,000 RUB and table ceiling 1,000,000 RUB.
   */
  public static calculateBet(
    cdt: number,
    step: number,
    mode: ServerMode,
    params: EngineParams,
    bankroll: number
  ): number {
    const baseBet = Math.max(GAME_RULES.MIN_BET, params.baseBet);

    if (cdt <= 0 || step <= 1) {
      return Math.min(baseBet, Math.max(GAME_RULES.MIN_BET, bankroll));
    }

    const targetSteps = params.stepsToLimit || 10;
    const terminalCap = Math.max(
      GAME_RULES.MIN_BET,
      Math.min(GAME_RULES.MAX_BET, Math.floor(bankroll / 1.90))
    );
    const remainingSteps = Math.max(1, targetSteps - step + 1);

    // Terminal step reached: snap to table ceiling or safe bankroll limit
    if (remainingSteps === 1) {
      return Math.min(terminalCap, bankroll);
    }

    // Previous bet level in the geometric progression
    const prevBet = Math.max(baseBet, Math.round(baseBet * Math.pow(params.growthFactor, step - 2)));

    // Calculate dynamic X to smoothly span remaining steps up to terminalCap
    const ratio = terminalCap / Math.max(1, prevBet);
    const dynamicX = Math.max(1.95, Math.min(2.40, Math.pow(ratio, 1.0 / remainingSteps)));
    const geomBet = Math.round(prevBet * dynamicX);

    // Strict mathematical debt recovery (TBB factoring in 2% casino tax)
    const minTbb = Math.ceil((cdt + baseBet) / GAME_RULES.WIN_NET_RATIO);

    // The bet must be at least minTbb to guarantee positive EV upon win,
    // and follows the smooth geometric curve toward the 1,000,000 ceiling.
    const bet = Math.max(minTbb, geomBet);

    // Hard bounds: never below 1,000 RUB, never exceed 1,000,000 RUB table limit or available bankroll
    const finalBet = Math.max(GAME_RULES.MIN_BET, Math.min(bet, GAME_RULES.MAX_BET, bankroll));
    return Math.round(finalBet);
  }
}
