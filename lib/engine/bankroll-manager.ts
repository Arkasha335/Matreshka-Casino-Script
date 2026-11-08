import { AggressionProfile, BetCalculationResult, EngineSettings, Outcome, ServerMode, SpinRecord } from './types';
import { RiskGuard } from './risk-guard';

export class BankrollManager {
  /**
   * Determine base bet based on bankroll and aggression profile.
   */
  public static getRecommendedBaseBet(bankroll: number, profile: AggressionProfile): number {
    let pct: number;
    switch (profile) {
      case 'HIGH_ROLLER_MAX':
        pct = 0.012; // 1.2% base bet for high-profit scaling
        break;
      case 'BALANCED_QUANT':
        pct = 0.006; // 0.6% base bet
        break;
      case 'CONSERVATIVE_SHIELD':
      default:
        pct = 0.003; // 0.3% base bet
        break;
    }
    const computed = Math.round(bankroll * pct);
    // Floor to nearest 500 or 1000
    const rounded = Math.max(1000, Math.round(computed / 500) * 500);
    return rounded;
  }

  /**
   * Calculate next bet amount and execution parameters.
   */
  public static calculateNextBet(
    currentBankroll: number,
    records: SpinRecord[],
    settings: EngineSettings,
    currentStep: number,
    surgeStep: number,
    cdt: number,
    currentMode: ServerMode
  ): BetCalculationResult {
    // 1. Evaluate Pre-Trade Risk Gates
    const risk = RiskGuard.evaluateRisk(records, settings, currentBankroll);

    if (risk.isHalted) {
      return {
        betAmount: 0,
        step: 1,
        surgeStep: 0,
        mode: 'DEFENSIVE',
        cdt: 0,
        isFrozen: true,
        freezeRemaining: 0,
        riskStatus: risk.reason === 'STOP_LOSS_TRIPPED' ? 'STOP_LOSS_TRIPPED' : 'TAKE_PROFIT_LOCKED',
        riskMessage: risk.message,
      };
    }

    if (risk.isZeroFreeze) {
      return {
        betAmount: 0,
        step: currentStep,
        surgeStep: 0,
        mode: 'FREEZE',
        cdt,
        isFrozen: true,
        freezeRemaining: risk.freezeRemaining,
        riskStatus: 'ZERO_FREEZE',
        riskMessage: risk.message,
      };
    }

    // 2. Base Bet Determination
    const baseBet = settings.baseBetOverride && settings.baseBetOverride > 0
      ? settings.baseBetOverride
      : this.getRecommendedBaseBet(settings.initialBankroll, settings.aggressionProfile);

    // 3. Mode Adjustment
    let modeMultiplier = 1.0;
    if (currentMode === 'HARVEST') {
      modeMultiplier = settings.aggressionProfile === 'HIGH_ROLLER_MAX' ? 1.25 : 1.1;
    } else if (currentMode === 'DEFENSIVE') {
      modeMultiplier = 0.6;
    }

    const effectiveBase = Math.max(1000, Math.round((baseBet * modeMultiplier) / 500) * 500);

    // 4. Staking Logic: Surge (Winning Wave) vs Recovery (Losing Step)
    let betAmount = effectiveBase;
    let newStep = currentStep;
    let newSurgeStep = surgeStep;
    let riskStatus: BetCalculationResult['riskStatus'] = 'NORMAL';
    let riskMessage = 'Стандартная ставка';

    // Case A: Deficit Recovery Mode (cdt > 0)
    if (cdt > 0) {
      newSurgeStep = 0; // Reset win streak surge

      if (currentStep <= settings.maxStepCap) {
        // Staged Bounded Martingale
        // Target Balance Bet to recover cdt + baseBet
        const tbb = Math.round((cdt + effectiveBase) / 0.98);
        
        let multiplier = 2.1;
        if (settings.aggressionProfile === 'HIGH_ROLLER_MAX') {
          multiplier = 2.2;
        } else if (settings.aggressionProfile === 'CONSERVATIVE_SHIELD') {
          multiplier = 2.0;
        }

        const geom = Math.round(effectiveBase * Math.pow(multiplier, currentStep - 1));
        betAmount = Math.max(tbb, geom);
        riskStatus = 'NORMAL';
        riskMessage = `Ступень покрытия дефицита ${currentStep}/${settings.maxStepCap}`;
      } else {
        // SOFT PIVOT: Amortized D'Alembert Deficit Spreading
        // If we exceeded maxStepCap, DO NOT double into liquidation. Spread cdt across 6 wins.
        const amortizedPortion = Math.round(cdt / 6);
        betAmount = effectiveBase + amortizedPortion;
        riskStatus = 'AMORTIZING';
        riskMessage = `Мягкая амортизация дефицита: защита от ликвидации (CDT: ${cdt.toLocaleString('ru-RU')} ₽)`;
      }
    } else {
      // Case B: No Deficit (cdt === 0) -> Check Surge Wave Riding
      newStep = 1;
      
      if (settings.surgeCompoundEnabled && surgeStep > 0) {
        // High-Roller Surge: Scale up on house profits
        // Surge multipliers: Step 1 (base), Step 2 (1.8x), Step 3 (3.2x), Step 4 (5.5x), then reset
        const surgeMultipliers = settings.aggressionProfile === 'HIGH_ROLLER_MAX'
          ? [1.0, 1.8, 3.2, 5.5]
          : [1.0, 1.5, 2.2];

        if (surgeStep < surgeMultipliers.length) {
          betAmount = Math.round(effectiveBase * surgeMultipliers[surgeStep]);
          riskStatus = 'SURGE_COMPOUND';
          riskMessage = `ВОЛНА ПРИБЫЛИ (Surge x${surgeMultipliers[surgeStep]}): агрессивный разгон на профите казино`;
        } else {
          // Surge cycle finished: lock profits and return to base
          betAmount = effectiveBase;
          newSurgeStep = 0;
          riskStatus = 'NORMAL';
          riskMessage = 'Цикл волны завершен с прибылью. Фиксация и возврат к базе.';
        }
      } else {
        betAmount = effectiveBase;
        riskStatus = 'NORMAL';
        riskMessage = 'Базовая квантовая ставка';
      }
    }

    // 5. Final Safety Hard Bounds
    // Never bet more than 10% of current bankroll in a single spin
    const maxSingleBetLimit = Math.min(1000000, currentBankroll * 0.12);
    if (betAmount > maxSingleBetLimit) {
      betAmount = Math.round(maxSingleBetLimit);
    }
    if (betAmount > currentBankroll) {
      betAmount = currentBankroll;
    }
    if (betAmount > 1000000) {
      betAmount = 1000000; // Table limit
    }
    betAmount = Math.max(1000, Math.round(betAmount));

    return {
      betAmount,
      step: newStep,
      surgeStep: newSurgeStep,
      mode: currentMode,
      cdt,
      isFrozen: false,
      freezeRemaining: 0,
      riskStatus,
      riskMessage,
    };
  }

  /**
   * Process spin outcome and update step, surgeStep, and cdt.
   */
  public static processOutcome(
    outcome: Outcome,
    recommendedColor: Outcome,
    betAmount: number,
    currentStep: number,
    surgeStep: number,
    cdt: number,
    isFrozen: boolean
  ): {
    isWin: boolean;
    netProfit: number;
    nextStep: number;
    nextSurgeStep: number;
    nextCdt: number;
  } {
    if (isFrozen || betAmount <= 0) {
      // Observation spin during Zero Freeze
      return {
        isWin: false,
        netProfit: 0,
        nextStep: currentStep,
        nextSurgeStep: 0,
        nextCdt: cdt,
      };
    }

    if (outcome === 'ZERO') {
      return {
        isWin: false,
        netProfit: -betAmount,
        nextStep: currentStep + 1,
        nextSurgeStep: 0,
        nextCdt: cdt + betAmount,
      };
    }

    const isWin = outcome === recommendedColor;
    if (isWin) {
      const netProfit = betAmount * 0.98; // 2% casino tax
      let nextCdt = Math.max(0, cdt - netProfit);
      if (nextCdt < 50) nextCdt = 0;

      let nextStep = currentStep;
      let nextSurgeStep = surgeStep + 1;

      if (nextCdt === 0) {
        nextStep = 1;
      }

      return {
        isWin: true,
        netProfit,
        nextStep,
        nextSurgeStep,
        nextCdt,
      };
    } else {
      return {
        isWin: false,
        netProfit: -betAmount,
        nextStep: currentStep + 1,
        nextSurgeStep: 0,
        nextCdt: cdt + betAmount,
      };
    }
  }
}
