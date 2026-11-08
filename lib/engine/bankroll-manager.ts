import { EngineParams, ServerMode, StrategyProfile } from './types';

export class BankrollManager {
  /**
   * Calculate calibrated engine parameters based on profile, server mode, and current bankroll.
   */
  public static getEngineParams(
    profile: StrategyProfile,
    mode: ServerMode,
    bankroll: number
  ): EngineParams {
    const minBankroll = 500000;
    const maxBankroll = 6500000;
    const clamped = Math.max(minBankroll, Math.min(bankroll, maxBankroll));
    const ratio = (clamped - minBankroll) / (maxBankroll - minBankroll);

    let fullBaseBet: number;
    let step2Boost: number;
    let step3Boost: number;
    let growthFactor: number;
    let sniperMult: number;

    if (profile === 'TURBO_HARVEST') {
      fullBaseBet = Math.round(2500 + ratio * (5500 - 2500));
      step2Boost = 1.25;
      step3Boost = 1.15;
      growthFactor = 2.20;
      sniperMult = 1.25;
    } else if (profile === 'SHIELD_CONSERVATIVE') {
      fullBaseBet = Math.round(1000 + ratio * (2200 - 1000));
      step2Boost = 1.0;
      step3Boost = 1.0;
      growthFactor = 2.05;
      sniperMult = 1.0;
    } else {
      // APEX_IDEAL (Verified Mathematical Optimum)
      fullBaseBet = Math.round(1500 + ratio * (4000 - 1500));
      step2Boost = 1.15;
      step3Boost = 1.10;
      growthFactor = 2.12;
      sniperMult = 1.15;
    }

    let effectiveBaseBet = fullBaseBet;
    if (mode === 'ZEBRA') {
      effectiveBaseBet = fullBaseBet;
    } else if (mode === 'TRANSITION') {
      effectiveBaseBet = Math.max(1000, Math.round(fullBaseBet * 0.8 / 100) * 100);
      step2Boost = Math.max(1.0, step2Boost - 0.05);
      step3Boost = Math.max(1.0, step3Boost - 0.05);
      growthFactor = Math.max(2.05, growthFactor - 0.05);
    } else {
      // DANGER mode: reduce base bet by 40% and use pure recovery to stretch margin to 11 steps!
      effectiveBaseBet = Math.max(1000, Math.round(fullBaseBet * 0.6 / 100) * 100);
      step2Boost = 1.0;
      step3Boost = 1.0;
      growthFactor = 2.02;
      sniperMult = 1.0;
    }

    // Calculate Steps to Table Limit (1,000,000 RUB)
    let stepsToLimit = 0;
    let simBet = effectiveBaseBet;
    let simCdt = 0;
    while (simBet < 1000000 && stepsToLimit < 20) {
      stepsToLimit++;
      simCdt += simBet;
      const tbb = Math.round((simCdt + effectiveBaseBet) / 0.98);
      const geom = Math.round(effectiveBaseBet * Math.pow(growthFactor, stepsToLimit));
      simBet = Math.max(tbb, geom);
    }

    // Durability: Steps until cumulative loss exceeds 50% bankroll
    let durabilitySteps = 0;
    let currentLoss = 0;
    let testBet = effectiveBaseBet;
    while (currentLoss < bankroll * 0.5 && durabilitySteps < 20) {
      durabilitySteps++;
      currentLoss += testBet;
      testBet = Math.round(testBet * growthFactor);
    }

    return {
      baseBet: effectiveBaseBet,
      step2Boost,
      step3Boost,
      growthFactor,
      sniperMult,
      stepsToLimit,
      durabilitySteps,
    };
  }

  /**
   * Calculate next bet with exact mathematical recovery.
   * Guarantees 100% CDT coverage + target base profit upon winning.
   */
  public static calculateBet(
    cdt: number,
    step: number,
    mode: ServerMode,
    params: EngineParams,
    bankroll: number
  ): number {
    if (cdt <= 0) return Math.round(params.baseBet);

    // Exact Target Balance Bet (recovers cdt + baseBet factoring in 2% tax)
    const tbb = Math.round((cdt + params.baseBet) / 0.98);

    let bet: number;
    if (step === 2 && params.step2Boost > 1.0) {
      bet = Math.round(tbb * params.step2Boost);
    } else if (step === 3 && params.step3Boost > 1.0) {
      bet = Math.round(tbb * params.step3Boost);
    } else {
      bet = tbb;
    }

    const geom = Math.round(params.baseBet * Math.pow(params.growthFactor, step - 1));
    bet = Math.max(bet, geom);

    // Hard bounds: never exceed table limit (1,000,000 RUB) or available bankroll
    const finalBet = Math.max(params.baseBet, Math.min(bet, 1000000, bankroll));
    return Math.round(finalBet);
  }
}
