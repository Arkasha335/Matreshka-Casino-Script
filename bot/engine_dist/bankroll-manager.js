"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.BankrollManager = void 0;
const types_1 = require("./types");
class BankrollManager {
    /**
     * Symmetric integer payout rounding under 2% commission.
     * Avoids systematic -0.5 RUB/win floor drift (-27..-38 RUB/session observed on Nov 11 logs).
     */
    static calcNetWin(bet) {
        const intBet = Math.max(0, Math.floor(bet));
        return Math.round((intBet * 98) / 100);
    }
    /**
     * Detects server ZERO burst inside recent window or active recovery sequence (v14.0 Zero-Shock Guard).
     */
    static isZeroShockActive(zeroCountLast10, zeroInSequence) {
        return zeroCountLast10 >= 2 || zeroInSequence >= 2;
    }
    /**
     * Determines whether the current sequence should lock into ZEBRA harvesting mode
     * to prevent premature EV degradation during temporary variance inside a deep wallet.
     * Unlocks automatically when Zero-Shock Guard detects a ZERO burst.
     */
    static shouldLockZebra(profile, cycleCapital, sequenceStartMode, isZeroShock = false) {
        if (isZeroShock)
            return false;
        return (profile !== 'SHIELD_CONSERVATIVE' &&
            cycleCapital >= this.ZEBRA_LOCK_CAPITAL_THRESHOLD &&
            sequenceStartMode === 'ZEBRA');
    }
    /**
     * Aggressive/Balanced v13.0 profiles exit DANGER immediately via fast detection
     * (skipping the 3+5 spin post-DANGER cooldown penalty); SHIELD preserves conservative hysteresis.
     */
    static usesFastModeDetector(profile) {
        return profile !== 'SHIELD_CONSERVATIVE';
    }
    static geomSumFactor(n, x = this.MIN_SOLVER_X) {
        return (Math.pow(x, n) - 1.0) / (x - 1.0);
    }
    /**
     * Terminal Sequence Loss Check:
     * Returns true if a lost bet marks the end of the recovery ladder:
     * 1) Table ceiling reached: effectiveBet >= GAME_RULES.MAX_BET (1,000,000 RUB).
     * 2) Target step budget exhausted: sequenceTargetSteps is defined and currentStep >= sequenceTargetSteps.
     * When true, the sequence is written off as a realized loss:
     * CDT is wiped to 0 and progression restarts cleanly from Step 1 (base bet).
     */
    static isTerminalSequenceLoss(currentStep, sequenceTargetSteps, effectiveBet, tableLimit = types_1.GAME_RULES.MAX_BET) {
        if (effectiveBet !== undefined && effectiveBet >= tableLimit) {
            return true;
        }
        if (sequenceTargetSteps !== undefined && sequenceTargetSteps > 0 && currentStep >= sequenceTargetSteps) {
            return true;
        }
        return false;
    }
    /**
     * Calibrated v15.1 Commercial Farm Matrix strictly bounded by GAME_RULES.MAX_BET (1,000,000 RUB):
     * - SHIELD_FORTRESS: Dynamic Tiered Micro-Harvest (N=10/10/10) with +80% higher yield at >=2.5M capital (2.5k/1.8k/1.2k)
     * - APEX_FARM: The 100% Automated Gold Standard for Multi-Account Farms (N=8/10/10, 4.5k/2.5k/1.4k >=3.5M; 4.0k/2.2k/1.2k <3.5M)
     * - TURBO_VELOCITY: Calibrated N=8/9/10 (6.5k/4.0k/2.0k >=3M; 4.5k/3.0k/1.5k <3M) - prevents premature sequence busts while maximizing EV
     */
    static getCalibratedLadderConfig(profile, mode, cycleCapital) {
        const cap = Math.max(types_1.GAME_RULES.MIN_BET * 10, cycleCapital);
        const limit = types_1.GAME_RULES.MAX_BET;
        const effectiveCeiling = Math.min(limit, cap / this.CYCLE_COST_FACTOR);
        const scale = Math.max(0.15, effectiveCeiling / 1000000);
        let nominalB0;
        let targetSteps;
        if (profile === 'SHIELD_CONSERVATIVE') {
            // v15.1 SHIELD_FORTRESS: Dynamic Tiered Micro-Harvest
            targetSteps = 10;
            if (cap >= 2500000) {
                nominalB0 = mode === 'ZEBRA' ? 2500 : mode === 'TRANSITION' ? 1800 : 1200;
            }
            else if (cap >= 1500000) {
                nominalB0 = mode === 'ZEBRA' ? 2000 : mode === 'TRANSITION' ? 1400 : 1000;
            }
            else {
                nominalB0 = mode === 'ZEBRA' ? 1400 : mode === 'TRANSITION' ? 1100 : 1000;
            }
        }
        else if (profile === 'TURBO_HARVEST') {
            // v15.1 TURBO_VELOCITY: Calibrated N=8/9/10
            if (cap >= 3000000) {
                if (mode === 'ZEBRA') {
                    nominalB0 = 6500;
                    targetSteps = 8;
                }
                else if (mode === 'TRANSITION') {
                    nominalB0 = 4000;
                    targetSteps = 9;
                }
                else {
                    nominalB0 = 2000;
                    targetSteps = 10;
                }
            }
            else {
                if (mode === 'ZEBRA') {
                    nominalB0 = 4500;
                    targetSteps = 8;
                }
                else if (mode === 'TRANSITION') {
                    nominalB0 = 3000;
                    targetSteps = 9;
                }
                else {
                    nominalB0 = 1500;
                    targetSteps = 10;
                }
            }
        }
        else {
            // v15.1 APEX_FARM: The Automated Gold Standard for Multi-Account Farms
            if (cap >= 3500000) {
                if (mode === 'ZEBRA') {
                    nominalB0 = 4500;
                    targetSteps = 8;
                }
                else if (mode === 'TRANSITION') {
                    nominalB0 = 2500;
                    targetSteps = 10;
                }
                else {
                    nominalB0 = 1400;
                    targetSteps = 10;
                }
            }
            else {
                if (mode === 'ZEBRA') {
                    nominalB0 = 4000;
                    targetSteps = 8;
                }
                else if (mode === 'TRANSITION') {
                    nominalB0 = 2200;
                    targetSteps = 10;
                }
                else {
                    nominalB0 = 1200;
                    targetSteps = 10;
                }
            }
        }
        // Reduce targetSteps if minimum 1,000 RUB ladder cannot fit in current capital
        while (targetSteps > 5 && types_1.GAME_RULES.MIN_BET * this.geomSumFactor(targetSteps) > cap) {
            targetSteps--;
        }
        // Guarantee baseBet never exceeds maximum budget-viable B0 for targetSteps at 2.025x
        const maxB0ForBudget = Math.max(types_1.GAME_RULES.MIN_BET, Math.floor(cap / this.geomSumFactor(targetSteps) / 100) * 100);
        const scaledB0 = Math.max(types_1.GAME_RULES.MIN_BET, Math.min(limit, maxB0ForBudget, Math.round((nominalB0 * scale) / 100) * 100));
        return {
            baseBet: scaledB0,
            targetSteps,
        };
    }
    /**
     * Exact Geometric Budget Solver (via 25-step binary search):
     * Finds the highest growth factor X such that:
     * 1) Future geometric bets B_j = prevB * X^j (j = 1..remSteps) stay <= tableLimit (1,000,000 RUB)
     * 2) Cumulative remaining spend sum_{j=1..remSteps} B_j <= remWallet
     */
    static solveExactBudgetX(prevB, remSteps, remWallet, tableLimit = types_1.GAME_RULES.MAX_BET) {
        const safePrev = Math.max(1, prevB);
        const steps = Math.max(1, remSteps);
        const limit = Math.min(types_1.GAME_RULES.MAX_BET, Math.max(types_1.GAME_RULES.MIN_BET, tableLimit));
        const wallet = Math.max(0, remWallet);
        const xTable = Math.pow(limit / safePrev, 1.0 / steps);
        let hi = Math.min(this.MAX_SOLVER_X, xTable);
        const geomSum = (x) => {
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
                    projectedTerminalBet: Math.min(limit, Math.floor(wallet)),
                };
            }
            let lo = 1.01;
            let hiFallback = this.MIN_SOLVER_X;
            if (geomSum(lo) > wallet) {
                return {
                    growthFactor: lo,
                    projectedTerminalBet: Math.min(limit, Math.floor(wallet)),
                };
            }
            for (let i = 0; i < 25; i++) {
                const mid = 0.5 * (lo + hiFallback);
                if (geomSum(mid) <= wallet)
                    lo = mid;
                else
                    hiFallback = mid;
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
                    projectedTerminalBet: Math.min(limit, Math.floor(wallet)),
                };
            }
            let hiW = this.MIN_SOLVER_X;
            for (let i = 0; i < 25; i++) {
                const mid = 0.5 * (lo + hiW);
                if (geomSum(mid) <= wallet)
                    lo = mid;
                else
                    hiW = mid;
            }
            return {
                growthFactor: lo,
                projectedTerminalBet: Math.min(limit, Math.round(safePrev * Math.pow(lo, steps))),
            };
        }
        lo = this.MIN_SOLVER_X;
        for (let i = 0; i < 25; i++) {
            const mid = 0.5 * (lo + hi);
            if (geomSum(mid) <= wallet)
                lo = mid;
            else
                hi = mid;
        }
        return {
            growthFactor: lo,
            projectedTerminalBet: Math.min(limit, Math.round(safePrev * Math.pow(lo, steps))),
        };
    }
    /**
     * Builds live EngineParams using cycleCapital (bankroll + cdt) strictly under 1,000,000 RUB table ceiling.
     */
    static getEngineParams(profile, mode, bankroll, cdt = 0, lockedTargetSteps, isZeroShock = false, currentStep = 1) {
        const limit = types_1.GAME_RULES.MAX_BET;
        const cycleCapital = Math.max(types_1.GAME_RULES.MIN_BET * 10, Math.floor(bankroll) + Math.max(0, cdt));
        const cfg = this.getCalibratedLadderConfig(profile, mode, cycleCapital);
        let targetSteps = cfg.targetSteps;
        if (lockedTargetSteps !== undefined && lockedTargetSteps > 0) {
            targetSteps =
                isZeroShock && currentStep >= 2
                    ? Math.min(10, Math.max(cfg.targetSteps, lockedTargetSteps), cfg.targetSteps)
                    : Math.min(cfg.targetSteps, lockedTargetSteps);
        }
        const effectiveBaseBet = Math.max(types_1.GAME_RULES.MIN_BET, Math.min(cfg.baseBet, cycleCapital, limit));
        const remStepsFromStart = Math.max(1, targetSteps - 1);
        const sol = this.solveExactBudgetX(effectiveBaseBet, remStepsFromStart, Math.max(0, cycleCapital - effectiveBaseBet), limit);
        let durabilitySteps = 0;
        let simCdt = 0;
        let simWallet = cycleCapital;
        let simPrev = undefined;
        for (let s = 1; s <= 15; s++) {
            if (simWallet < types_1.GAME_RULES.MIN_BET)
                break;
            const nextB = this.calculateBet(simCdt, s, mode, {
                baseBet: effectiveBaseBet,
                step2Boost: 1,
                step3Boost: 1,
                growthFactor: sol.growthFactor,
                sniperMult: 1,
                stepsToLimit: targetSteps,
                durabilitySteps: targetSteps,
                tableLimit: limit,
            }, simWallet, simPrev);
            if (nextB < types_1.GAME_RULES.MIN_BET || nextB > simWallet)
                break;
            durabilitySteps++;
            simCdt += nextB;
            simWallet -= nextB;
            simPrev = nextB;
            if (s >= targetSteps || nextB >= limit)
                break;
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
     * Computes exact next wager using the Exact Geometric Budget Solver + Exact Floor Commission Recovery
     * + Penultimate Horizon Guard strictly bounded by GAME_RULES.MAX_BET (1,000,000 RUB).
     */
    static calculateBet(cdt, step, _mode, params, bankroll, prevBet) {
        const intWallet = Math.floor(bankroll);
        if (intWallet <= 0)
            return 0;
        if (intWallet < types_1.GAME_RULES.MIN_BET)
            return intWallet;
        const limit = types_1.GAME_RULES.MAX_BET;
        const baseBet = Math.max(types_1.GAME_RULES.MIN_BET, Math.min(Math.floor(params.baseBet), intWallet, limit));
        if (cdt <= 0 || step <= 1) {
            return baseBet;
        }
        const targetSteps = Math.max(1, params.stepsToLimit || 10);
        if (step > targetSteps) {
            // Safety guard: step exceeded allocated sequence horizon.
            // Reset to baseBet to prevent runaway flat-ceiling bets.
            return baseBet;
        }
        const rem = Math.max(1, targetSteps - step + 1);
        // Ensure server's floored net payout strictly covers cumulative debt + baseBet
        let minTbb = Math.ceil(((cdt + baseBet) * 100) / 98);
        while (this.calcNetWin(minTbb) < cdt + baseBet) {
            minTbb++;
        }
        const pb = prevBet !== undefined && prevBet > 0
            ? Math.floor(prevBet)
            : Math.max(baseBet, Math.round(baseBet * Math.pow(params.growthFactor, Math.max(0, step - 2))));
        if (rem === 1) {
            const cap = Math.min(limit, intWallet);
            const finalTerminal = cdt < cap * 0.30 ? Math.min(minTbb, cap) : cap;
            return Math.max(types_1.GAME_RULES.MIN_BET, Math.min(cap, Math.floor(finalTerminal)));
        }
        const { growthFactor } = this.solveExactBudgetX(pb, rem, intWallet, limit);
        const geomBet = Math.round(pb * growthFactor);
        let bet = Math.max(minTbb, geomBet);
        // Penultimate Horizon Guard (rem === 2):
        // Ensures CDT + bet stays within floored final-step recovery capacity of 1,000,000 RUB or wallet.
        if (rem === 2) {
            const maxPenTable = this.calcNetWin(limit) - cdt - 100;
            const maxPenWallet = Math.floor((0.98 * intWallet - cdt - 100) / 1.98);
            const maxSafe = Math.min(maxPenTable, maxPenWallet);
            let minBreakeven = Math.ceil(((cdt + 100) * 100) / 98);
            while (this.calcNetWin(minBreakeven) < cdt + 100) {
                minBreakeven++;
            }
            if (maxSafe >= minBreakeven) {
                bet = Math.min(bet, maxSafe);
            }
        }
        return Math.max(types_1.GAME_RULES.MIN_BET, Math.min(Math.floor(bet), limit, intWallet));
    }
}
exports.BankrollManager = BankrollManager;
BankrollManager.MIN_SOLVER_X = 2.025;
BankrollManager.MAX_SOLVER_X = 3.20;
BankrollManager.CYCLE_COST_FACTOR = 1.92;
BankrollManager.ZEBRA_LOCK_CAPITAL_THRESHOLD = 3000000;
