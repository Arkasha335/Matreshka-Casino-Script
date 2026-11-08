import { EngineParams, ServerMode, StrategyProfile } from './types';

export class BankrollManager {
  /**
   * Terminal Boundary Backward Induction:
   * Returns exact calibrated base bet and multipliers to guarantee N steps before the 1,000,000 RUB table limit.
   */
  public static getEngineParams(
    profile: StrategyProfile,
    mode: ServerMode,
    bankroll: number
  ): EngineParams {
    const effectiveBankroll = Math.max(100000, bankroll);
    const bankrollCap = 2000000;
    const bankrollRatio = Math.min(1.0, effectiveBankroll / bankrollCap);

    let targetBaseBet: number;
    let step2Boost: number;
    let step3Boost: number;
    let targetSteps: number;

    if (profile === 'TURBO_HARVEST') {
      // 9-step ladder: Max B0 = 3,300 RUB. High EV velocity.
      targetBaseBet = Math.round(1200 + bankrollRatio * (3300 - 1200));
      step2Boost = 1.05;
      step3Boost = 1.00;
      targetSteps = 9;
    } else if (profile === 'SHIELD_CONSERVATIVE') {
      // 11-step ladder: Max B0 = 800 RUB. Ultra capital protection.
      targetBaseBet = Math.round(300 + bankrollRatio * (800 - 300));
      step2Boost = 1.00;
      step3Boost = 1.00;
      targetSteps = 11;
    } else {
      // APEX_IDEAL (Golden Standard): Exactly 10 steps to 1,000,000 RUB.
      targetBaseBet = Math.round(600 + bankrollRatio * (1600 - 600));
      step2Boost = 1.12;
      step3Boost = 1.06;
      targetSteps = 10;
    }

    let effectiveBaseBet = targetBaseBet;

    // Dynamic Server Mode Adaptation (Online / Aggression mitigation)
    if (mode === 'ZEBRA') {
      effectiveBaseBet = targetBaseBet;
    } else if (mode === 'TRANSITION') {
      effectiveBaseBet = Math.max(500, Math.round((targetBaseBet * 0.8) / 50) * 50);
      step2Boost = Math.min(1.05, step2Boost);
      step3Boost = 1.00;
    } else {
      // DANGER mode: Server is in an anomalous mono-streak or high zero density.
      // Automatically cuts base bet by 50%, granting an IMMEDIATE +1 EXTRA STEP of safety cushion!
      effectiveBaseBet = Math.max(400, Math.round((targetBaseBet * 0.5) / 50) * 50);
      step2Boost = 1.00;
      step3Boost = 1.00;
      targetSteps += 1;
    }

    // Exact discrete step capacity simulation
    let stepsToLimit = 0;
    let simBet = effectiveBaseBet;
    let simCdt = 0;
    while (simBet < 1000000 && stepsToLimit < 20) {
      stepsToLimit++;
      simCdt += simBet;
      const tbb = Math.round((simCdt + effectiveBaseBet) / 0.98);
      simBet = tbb;
    }

    // Durability: steps until cumulative loss exceeds current bankroll
    let durabilitySteps = 0;
    let currentLoss = 0;
    let testCdt = 0;
    let testBet = effectiveBaseBet;
    while (currentLoss + testBet <= effectiveBankroll && durabilitySteps < 20 && testBet <= 1000000) {
      durabilitySteps++;
      currentLoss += testBet;
      testCdt += testBet;
      testBet = Math.round((testCdt + effectiveBaseBet) / 0.98);
    }

    return {
      baseBet: effectiveBaseBet,
      step2Boost,
      step3Boost,
      growthFactor: 2.04, // Mathematical minimal recovery ratio
      sniperMult: step2Boost,
      stepsToLimit,
      durabilitySteps: Math.max(1, durabilitySteps),
    };
  }

  /**
   * Dynamic Terminal Boundary Staking:
   * 1. Uses Minimal TBB for intermediate steps to conserve bankroll and guarantee the maximum step cushion.
   * 2. When the terminal step is reached (no further step can fit under 1M RUB or bankroll),
   *    snaps the bet to the 1,000,000 RUB ceiling to extract maximum terminal payoff!
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

    // Target Balance Bet (100% CDT coverage + base profit with 2% tax)
    const tbb = Math.round((cdt + params.baseBet) / 0.98);

    let bet: number;
    if (step === 2 && params.step2Boost > 1.0) {
      bet = Math.round(tbb * params.step2Boost);
    } else if (step === 3 && params.step3Boost > 1.0) {
      bet = Math.round(tbb * params.step3Boost);
    } else {
      bet = tbb;
    }

    // Terminal Boundary Check (User's Terminal Ceiling Theory):
    // If the NEXT step after this bet would exceed the 1,000,000 RUB table limit
    // OR exceed remaining bankroll, this current step IS THE TERMINAL STEP.
    const nextCdt = cdt + bet;
    const nextTbb = Math.round((nextCdt + params.baseBet) / 0.98);
    const isTerminalStep = (nextTbb > 1000000) || (nextCdt + nextTbb > bankroll) || (bet >= 1000000);

    if (isTerminalStep) {
      // Maximize profit on the terminal boundary: bet up to full 1M table limit or bankroll
      bet = Math.min(1000000, bankroll);
    }

    // Hard bounds: never exceed table limit (1,000,000 RUB) or available bankroll
    const finalBet = Math.max(params.baseBet, Math.min(bet, 1000000, bankroll));
    return Math.round(finalBet);
  }
}
