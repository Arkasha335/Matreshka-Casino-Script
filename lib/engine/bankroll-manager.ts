import { EngineParams, ServerMode, StrategyProfile } from './types';

export class BankrollManager {
  /**
   * Dynamic Constant Multiplier Architecture:
   * Calculates the exact constant growth factor X = (B_terminal / B_0)^(1 / (N - 1))
   * such that the N-th step naturally lands directly on the 1,000,000 RUB table ceiling
   * or matches the bankroll boundary without arbitrary jumps.
   */
  public static getEngineParams(
    profile: StrategyProfile,
    mode: ServerMode,
    bankroll: number
  ): EngineParams {
    const effectiveBankroll = Math.max(100000, bankroll);
    const bankrollCap = 1900000;
    const bankrollRatio = Math.min(1.0, effectiveBankroll / bankrollCap);

    let targetSteps: number;
    let nominalBaseBet: number;

    if (profile === 'TURBO_HARVEST') {
      // 9 steps to 1,000,000 RUB limit. High EV velocity.
      targetSteps = 9;
      nominalBaseBet = 2000;
    } else if (profile === 'SHIELD_CONSERVATIVE') {
      // 11 steps to 1,000,000 RUB limit. Maximum capital preservation.
      targetSteps = 11;
      nominalBaseBet = 600;
    } else {
      // APEX_IDEAL (Golden Standard): Exactly 10 steps to 1,000,000 RUB limit.
      targetSteps = 10;
      nominalBaseBet = 1200;
    }

    // Dynamic Server Mode Adaptation (Online spikes & mono-streak defense)
    if (mode === 'DANGER') {
      // In DANGER mode: automatically grant +1 extra step of safety cushion
      // by lowering nominal base bet by 40% and increasing target steps by 1
      targetSteps += 1;
      nominalBaseBet = Math.max(500, Math.round((nominalBaseBet * 0.6) / 50) * 50);
    } else if (mode === 'TRANSITION') {
      nominalBaseBet = Math.max(500, Math.round((nominalBaseBet * 0.85) / 50) * 50);
    }

    // Scale base bet if bankroll cannot afford full 1.9M progression
    const effectiveBaseBet = Math.max(500, Math.round(nominalBaseBet * bankrollRatio / 50) * 50);

    // Terminal boundary: table limit (1,000,000) or bankroll-safe ceiling
    const terminalCap = Math.min(1000000, Math.floor(effectiveBankroll / 1.90));

    // Calculate exact constant multiplier X
    const ratio = terminalCap / Math.max(1, effectiveBaseBet);
    const exponent = 1.0 / Math.max(1, targetSteps - 1);
    const dynamicMultiplier = Math.max(2.025, Math.min(2.40, Math.pow(ratio, exponent)));

    // Calculate steps until table limit (1,000,000 RUB)
    let stepsToLimit = 0;
    let simBet = effectiveBaseBet;
    let simCdt = 0;
    while (simBet <= 1000000 && stepsToLimit < 20) {
      stepsToLimit++;
      simCdt += simBet;
      simBet = Math.round(simBet * dynamicMultiplier);
    }

    // Calculate durability steps until bankroll exhausted
    let durabilitySteps = 0;
    let cumLoss = 0;
    let testBet = effectiveBaseBet;
    while (cumLoss + testBet <= effectiveBankroll && durabilitySteps < 20 && testBet <= 1000000) {
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
   */
  public static calculateBet(
    cdt: number,
    step: number,
    mode: ServerMode,
    params: EngineParams,
    bankroll: number
  ): number {
    if (cdt <= 0 || step <= 1) {
      return Math.min(params.baseBet, bankroll);
    }

    const targetSteps = params.stepsToLimit || 10;
    const terminalCap = Math.min(1000000, Math.floor(bankroll / 1.90));
    const remainingSteps = Math.max(1, targetSteps - step + 1);

    // Terminal step reached: snap to table ceiling or safe bankroll limit
    if (remainingSteps === 1) {
      return Math.min(terminalCap, bankroll);
    }

    // Previous bet level in the geometric progression
    const prevBet = Math.max(params.baseBet, Math.round(params.baseBet * Math.pow(params.growthFactor, step - 2)));

    // Calculate dynamic X to smoothly span remaining steps up to terminalCap
    const ratio = terminalCap / Math.max(1, prevBet);
    const dynamicX = Math.max(2.025, Math.min(2.40, Math.pow(ratio, 1.0 / remainingSteps)));
    const geomBet = Math.round(prevBet * dynamicX);

    // Strict mathematical debt recovery (TBB factoring in 2% casino tax)
    const minTbb = Math.ceil((cdt + params.baseBet) / 0.98);

    // The bet must be at least minTbb to guarantee positive EV upon win,
    // and follows the smooth geometric curve toward the 1,000,000 ceiling.
    const bet = Math.max(minTbb, geomBet);

    // Hard bounds: never exceed 1,000,000 RUB table limit or available bankroll
    const finalBet = Math.max(params.baseBet, Math.min(bet, 1000000, bankroll));
    return Math.round(finalBet);
  }
}
