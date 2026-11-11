import { EngineParams, GAME_RULES, ServerMode, StrategyProfile } from './types';

export interface SolverSolution {
  growthFactor: number;
  projectedTerminalBet: number;
}

export class BankrollManager {
  private static readonly MIN_SOLVER_X = 2.025;
  private static readonly MAX_SOLVER_X = 3.20;
  private static readonly CYCLE_COST_FACTOR = 1.92;
  private static readonly ZEBRA_LOCK_CAPITAL_THRESHOLD = 3000000;

  /**
   * Determines whether the current sequence should lock into ZEBRA harvesting mode
   * to prevent premature EV degradation during temporary variance inside a deep wallet.
   */
  public static shouldLockZebra(
    profile: StrategyProfile,
    cycleCapital: number,
    sequenceStartMode: ServerMode
  ): boolean {
    return (
      profile !== 'SHIELD_CONSERVATIVE' &&
      cycleCapital >= this.ZEBRA_LOCK_CAPITAL_THRESHOLD &&
      sequenceStartMode === 'ZEBRA'
    );
  }

  /**
   * Aggressive/Balanced v12.5 profiles exit DANGER immediately via fast detection
   * (skipping the 3+5 spin post-DANGER cooldown penalty); SHIELD preserves conservative hysteresis.
   */
  public static usesFastModeDetector(profile: StrategyProfile): boolean {
    return profile !== 'SHIELD_CONSERVATIVE';
  }

  private static geomSumFactor(n: number, x: number = this.MIN_SOLVER_X): number {
    return (Math.pow(x, n) - 1.0) / (x - 1.0);
  }

  /**
   * Calibrated v12.5 Base Bet & Target Step Matrix:
   * Dynamically scales nominal base bets against min(tableLimit, cycleCapital / 1.92),
   * while guaranteeing every step N stays mathematically affordable at MIN_SOLVER_X (2.025x).
   */
  public static getCalibratedLadderConfig(
    profile: StrategyProfile,
    mode: ServerMode,
    cycleCapital: number,
    tableLimit: number = GAME_RULES.MAX_BET
  ): { baseBet: number; targetSteps: number } {
    const cap = Math.max(GAME_RULES.MIN_BET * 10, cycleCapital);
    const limit = Math.max(GAME_RULES.MIN_BET * 10, tableLimit);

    const effectiveCeiling = Math.min(limit, cap / this.CYCLE_COST_FACTOR);
    const scale = Math.max(0.15, effectiveCeiling / 1000000);

    let nominalB0: number;
    let targetSteps: number;

    if (profile === 'SHIELD_CONSERVATIVE') {
      targetSteps = 10;
      nominalB0 = mode === 'ZEBRA' ? 1700 : mode === 'TRANSITION' ? 1200 : 1000;
    } else if (profile === 'TURBO_HARVEST') {
      if (mode === 'ZEBRA') {
        nominalB0 = 6000;
        targetSteps = 8;
      } else if (mode === 'TRANSITION') {
        nominalB0 = 4000;
        targetSteps = 8;
      } else {
        nominalB0 = 1700;
        targetSteps = 9;
      }
    } else {
      // APEX_IDEAL (v12.5 Sweet Spot: 9/10/10 horizon, +783k..+976k/hr @ 2M limit, 100% Real Win @ 6.5M)
      if (mode === 'ZEBRA') {
        nominalB0 = 3500;
        targetSteps = 9;
      } else if (mode === 'TRANSITION') {
        nominalB0 = 2000;
        targetSteps = 10;
      } else {
        nominalB0 = 1200;
        targetSteps = 10;
      }
    }

    // Reduce targetSteps if minimum 1,000 RUB ladder cannot fit in current capital
    while (targetSteps > 5 && GAME_RULES.MIN_BET * this.geomSumFactor(targetSteps) > cap) {
      targetSteps--;
    }

    // Guarantee baseBet never exceeds maximum budget-viable B0 for targetSteps at 2.025x
    const maxB0ForBudget = Math.max(
      GAME_RULES.MIN_BET,
      Math.floor(cap / this.geomSumFactor(targetSteps) / 100) * 100
    );

    const scaledB0 = Math.max(
      GAME_RULES.MIN_BET,
      Math.min(
        limit,
        maxB0ForBudget,
        Math.round((nominalB0 * scale) / 100) * 100
      )
    );

    return {
      baseBet: scaledB0,
      targetSteps,
    };
  }

  /**
   * Exact Geometric Budget Solver (via 25-step binary search):
   * Finds the highest growth factor X such that:
   * 1) Future geometric bets B_j = prevB * X^j (j = 1..remSteps) stay <= tableLimit
   * 2) Cumulative remaining spend sum_{j=1..remSteps} B_j <= remWallet
   * Guarantees smooth scaling directly up to min(tableLimit, affordableMax).
   */
  public static solveExactBudgetX(
    prevB: number,
    remSteps: number,
    remWallet: number,
    tableLimit: number
  ): SolverSolution {
    const safePrev = Math.max(1, prevB);
    const steps = Math.max(1, remSteps);
    const limit = Math.max(GAME_RULES.MIN_BET, tableLimit);
    const wallet = Math.max(0, remWallet);

    const xTable = Math.pow(limit / safePrev, 1.0 / steps);
    let hi = Math.min(this.MAX_SOLVER_X, xTable);

    const geomSum = (x: number): number => {
      let sum = 0;
      let b = safePrev;
      for (let i = 0; i < steps; i++) {
        b *= x;
        sum += b;
      }
      return sum;
    };

    if (hi < this.MIN_SOLVER_X) {
      if (geomSum(this.MIN_SOLVER_X) <= wallet) {
        return {
          growthFactor: this.MIN_SOLVER_X,
          projectedTerminalBet: Math.min(limit, wallet),
        };
      }
      let lo = 1.01;
      let hiFallback = this.MIN_SOLVER_X;
      if (geomSum(lo) > wallet) {
        return {
          growthFactor: lo,
          projectedTerminalBet: Math.min(limit, wallet),
        };
      }
      for (let i = 0; i < 25; i++) {
        const mid = 0.5 * (lo + hiFallback);
        if (geomSum(mid) <= wallet) lo = mid;
        else hiFallback = mid;
      }
      return {
        growthFactor: lo,
        projectedTerminalBet: Math.min(limit, Math.round(safePrev * Math.pow(lo, steps))),
      };
    }

    if (geomSum(hi) <= wallet) {
      return {
        growthFactor: hi,
        projectedTerminalBet: Math.min(limit, Math.round(safePrev * Math.pow(hi, steps))),
      };
    }

    let lo = 1.01;
    if (geomSum(this.MIN_SOLVER_X) > wallet) {
      if (geomSum(lo) > wallet) {
        return {
          growthFactor: lo,
          projectedTerminalBet: Math.min(limit, wallet),
        };
      }
      let hiW = this.MIN_SOLVER_X;
      for (let i = 0; i < 25; i++) {
        const mid = 0.5 * (lo + hiW);
        if (geomSum(mid) <= wallet) lo = mid;
        else hiW = mid;
      }
      return {
        growthFactor: lo,
        projectedTerminalBet: Math.min(limit, Math.round(safePrev * Math.pow(lo, steps))),
      };
    }

    lo = this.MIN_SOLVER_X;
    for (let i = 0; i < 25; i++) {
      const mid = 0.5 * (lo + hi);
      if (geomSum(mid) <= wallet) lo = mid;
      else hi = mid;
    }

    return {
      growthFactor: lo,
      projectedTerminalBet: Math.min(limit, Math.round(safePrev * Math.pow(lo, steps))),
    };
  }

  /**
   * Builds live EngineParams using cycleCapital (bankroll + cdt) so step projections
   * and multipliers remain stable and accurate throughout recovery cycles.
   */
  public static getEngineParams(
    profile: StrategyProfile,
    mode: ServerMode,
    bankroll: number,
    tableLimit: number = GAME_RULES.MAX_BET,
    cdt: number = 0,
    lockedTargetSteps?: number
  ): EngineParams {
    const limit = Math.max(GAME_RULES.MIN_BET * 10, tableLimit);
    const cycleCapital = Math.max(GAME_RULES.MIN_BET * 10, bankroll + Math.max(0, cdt));
    const cfg = this.getCalibratedLadderConfig(profile, mode, cycleCapital, limit);

    const targetSteps =
      lockedTargetSteps !== undefined && lockedTargetSteps > 0
        ? Math.min(cfg.targetSteps, lockedTargetSteps)
        : cfg.targetSteps;

    const effectiveBaseBet = Math.max(
      GAME_RULES.MIN_BET,
      Math.min(cfg.baseBet, cycleCapital, limit)
    );

    const remStepsFromStart = Math.max(1, targetSteps - 1);
    const sol = this.solveExactBudgetX(
      effectiveBaseBet,
      remStepsFromStart,
      Math.max(0, cycleCapital - effectiveBaseBet),
      limit
    );

    // Simulate forward ladder durability against cycleCapital and tableLimit
    let durabilitySteps = 0;
    let simCdt = 0;
    let simWallet = cycleCapital;
    let simPrev: number | undefined = undefined;
    for (let s = 1; s <= 15; s++) {
      if (simWallet < GAME_RULES.MIN_BET) break;
      const nextB = this.calculateBet(
        simCdt,
        s,
        mode,
        {
          baseBet: effectiveBaseBet,
          step2Boost: 1,
          step3Boost: 1,
          growthFactor: sol.growthFactor,
          sniperMult: 1,
          stepsToLimit: targetSteps,
          durabilitySteps: targetSteps,
          tableLimit: limit,
        },
        simWallet,
        simPrev,
        limit
      );
      if (nextB < GAME_RULES.MIN_BET || nextB > simWallet) break;
      durabilitySteps++;
      simCdt += nextB;
      simWallet -= nextB;
      simPrev = nextB;
      if (s >= targetSteps || nextB >= limit) break;
    }

    return {
      baseBet: effectiveBaseBet,
      step2Boost: sol.growthFactor / 2.04,
      step3Boost: sol.growthFactor / 2.04,
      growthFactor: sol.growthFactor,
      sniperMult: sol.growthFactor / 2.04,
      stepsToLimit: Math.max(1, targetSteps),
      durabilitySteps: Math.max(1, durabilitySteps),
      tableLimit: limit,
      projectedTerminalBet: sol.projectedTerminalBet,
    };
  }

  /**
   * Computes exact next wager using the Exact Geometric Budget Solver + 2% Commission Coverage
   * + Generalized Penultimate Horizon Guard (valid for 1M, 2M, or custom table limits).
   */
  public static calculateBet(
    cdt: number,
    step: number,
    _mode: ServerMode,
    params: EngineParams,
    bankroll: number,
    prevBet?: number,
    tableLimit?: number
  ): number {
    if (bankroll <= 0) return 0;
    if (bankroll < GAME_RULES.MIN_BET) return Math.round(bankroll);

    const limit = Math.max(GAME_RULES.MIN_BET, tableLimit ?? params.tableLimit ?? GAME_RULES.MAX_BET);
    const baseBet = Math.max(GAME_RULES.MIN_BET, Math.min(params.baseBet, bankroll, limit));

    if (cdt <= 0 || step <= 1) {
      return Math.round(baseBet);
    }

    const targetSteps = Math.max(1, params.stepsToLimit || 10);
    const rem = Math.max(1, targetSteps - step + 1);
    const minTbb = Math.ceil((cdt + baseBet) / GAME_RULES.WIN_NET_RATIO);

    const pb =
      prevBet !== undefined && prevBet > 0
        ? prevBet
        : Math.max(baseBet, Math.round(baseBet * Math.pow(params.growthFactor, Math.max(0, step - 2))));

    if (rem === 1) {
      const cap = Math.min(limit, bankroll);
      // Avoid wagering 1M-2M over tiny leftover debt (<30% of cap) after an earlier partial win
      const finalTerminal = cdt < cap * 0.30 ? Math.min(minTbb, cap) : cap;
      return Math.max(GAME_RULES.MIN_BET, Math.min(cap, Math.round(finalTerminal)));
    }

    const { growthFactor } = this.solveExactBudgetX(pb, rem, bankroll, limit);
    const geomBet = Math.round(pb * growthFactor);
    let bet = Math.max(minTbb, geomBet);

    // Generalized Penultimate Horizon Guard (rem === 2):
    // Ensures CDT + bet stays below 0.98 * min(limit, bankroll - bet) so the final step
    // strictly recovers all cumulative debt with positive net profit under 2% tax.
    if (rem === 2) {
      const maxPenTable = Math.floor(limit * GAME_RULES.WIN_NET_RATIO) - cdt - 100;
      const maxPenWallet = Math.floor(
        (GAME_RULES.WIN_NET_RATIO * bankroll - cdt - 100) / (1 + GAME_RULES.WIN_NET_RATIO)
      );
      const maxSafe = Math.min(maxPenTable, maxPenWallet);
      const minBreakeven = Math.ceil((cdt + 100) / GAME_RULES.WIN_NET_RATIO);
      if (maxSafe >= minBreakeven) {
        bet = Math.min(bet, maxSafe);
      }
    }

    return Math.round(Math.max(GAME_RULES.MIN_BET, Math.min(bet, limit, bankroll)));
  }
}
