import { ApexMatrix, HistoryEntry, Outcome, PredictionResult, ServerMode, SkewStats } from './types';

export class PrngDetector {
  /**
   * Calculate alternation rate over an array of history entries.
   */
  public static calcAlternation(arr: HistoryEntry[]): number {
    if (arr.length < 3) return 0.5;
    let transitions = 0;
    for (let i = 1; i < arr.length; i++) {
      if (arr[i].outcome !== arr[i - 1].outcome) transitions++;
    }
    return transitions / (arr.length - 1);
  }

  /**
   * Current active streak of non-zero entries.
   */
  public static calcCurrentStreak(nonZero: HistoryEntry[]): number {
    if (nonZero.length === 0) return 0;
    let streak = 1;
    const lastColor = nonZero[nonZero.length - 1].outcome;
    for (let i = nonZero.length - 2; i >= 0; i--) {
      if (nonZero[i].outcome === lastColor) streak++;
      else break;
    }
    return streak;
  }

  /**
   * Count streaks >= minLen in history.
   */
  public static countStreaksGTE(nonZero: HistoryEntry[], minLen: number): number {
    if (nonZero.length === 0) return 0;
    let count = 0;
    let currentStreak = 1;
    let lastColor = nonZero[0].outcome;

    for (let i = 1; i < nonZero.length; i++) {
      if (nonZero[i].outcome === lastColor) {
        currentStreak++;
      } else {
        if (currentStreak >= minLen) count++;
        currentStreak = 1;
        lastColor = nonZero[i].outcome;
      }
    }
    if (currentStreak >= minLen) count++;
    return count;
  }

  /**
   * Calculate Apex Matrix for Alpha/Omega, streak maximums and active streaks.
   */
  public static getApexMatrix(history: HistoryEntry[], window: number = 20): ApexMatrix {
    const nonZero = history.filter(h => h.outcome !== 'ZERO').slice(-window);

    let redCount = 0;
    let blackCount = 0;
    let maxStreakRed = 0;
    let maxStreakBlack = 0;

    let currentStreak = 0;
    let currentColor: Outcome | null = null;

    for (const h of nonZero) {
      if (h.outcome === 'RED') redCount++;
      if (h.outcome === 'BLACK') blackCount++;

      if (h.outcome === currentColor) {
        currentStreak++;
      } else {
        currentColor = h.outcome;
        currentStreak = 1;
      }

      if (currentColor === 'RED' && currentStreak > maxStreakRed) maxStreakRed = currentStreak;
      if (currentColor === 'BLACK' && currentStreak > maxStreakBlack) maxStreakBlack = currentStreak;
    }

    let alpha: Outcome | 'NEUTRAL' = 'NEUTRAL';
    let omega: Outcome | 'NEUTRAL' = 'NEUTRAL';

    if (nonZero.length > 0) {
      if (redCount / nonZero.length > 0.55) {
        alpha = 'RED';
        omega = 'BLACK';
      } else if (blackCount / nonZero.length > 0.55) {
        alpha = 'BLACK';
        omega = 'RED';
      }
    }

    let currentActiveStreak = 0;
    let currentActiveColor: Outcome | null = null;
    if (nonZero.length > 0) {
      currentActiveColor = nonZero[nonZero.length - 1].outcome;
      for (let i = nonZero.length - 1; i >= 0; i--) {
        if (nonZero[i].outcome === currentActiveColor) {
          currentActiveStreak++;
        } else {
          break;
        }
      }
    }

    return {
      alpha,
      omega,
      maxStreakRed,
      maxStreakBlack,
      currentActiveColor,
      currentActiveStreak,
    };
  }

  /**
   * Global color skew across entire session.
   */
  public static getGlobalSkew(history: HistoryEntry[]): SkewStats {
    const nonZero = history.filter(h => h.outcome !== 'ZERO');
    if (nonZero.length === 0) return { red: 50, black: 50, dominant: null };
    const redCount = nonZero.filter(h => h.outcome === 'RED').length;
    const redPct = (redCount / nonZero.length) * 100;
    const blackPct = 100 - redPct;
    let dominant: Outcome | null = null;
    if (Math.abs(redPct - blackPct) > 10) {
      dominant = redPct > blackPct ? 'RED' : 'BLACK';
    }
    return { red: redPct, black: blackPct, dominant };
  }

  /**
   * Local color skew over rolling window.
   */
  public static getLocalSkew(history: HistoryEntry[], window: number = 15): SkewStats {
    const nonZero = history.filter(h => h.outcome !== 'ZERO').slice(-window);
    if (nonZero.length === 0) return { red: 50, black: 50, dominant: null };
    const redCount = nonZero.filter(h => h.outcome === 'RED').length;
    const redPct = (redCount / nonZero.length) * 100;
    const blackPct = 100 - redPct;
    let dominant: Outcome | null = null;
    if (redCount >= 10) dominant = 'RED';
    else if (nonZero.length - redCount >= 10) dominant = 'BLACK';
    return { red: redPct, black: blackPct, dominant };
  }

  /**
   * Server Mode Detection: ZEBRA, TRANSITION, DANGER.
   */
  /**
   * Fast & Responsive Server Mode Detection:
   * - ZEBRA: High alternation rate (>= 60%), streaks <= 2, no recent Zero.
   * - TRANSITION ("Жёлтенький"): Streaks of 3-4, moderate alternation, or 1 recent Zero.
   * - DANGER: Aggressive mono-streaks (>= 5), cluster of ZEROs (>= 2 in 10), or streak >= 4 with low alternation.
   */
  public static detectMode(history: HistoryEntry[]): ServerMode {
    const nonZero = history.filter(h => h.outcome !== 'ZERO');
    if (nonZero.length < 3) return 'ZEBRA';

    const currentStreak = this.calcCurrentStreak(nonZero);
    const fastAltRate = this.calcAlternation(nonZero.slice(-6));
    const streak3plusCount = this.countStreaksGTE(nonZero.slice(-12), 3);
    const zeroCount10 = history.slice(-10).filter(h => h.outcome === 'ZERO').length;
    const zeroCount5 = history.slice(-5).filter(h => h.outcome === 'ZERO').length;

    // 1. DANGER Triggers (Immediate Reaction)
    if (currentStreak >= 5) return 'DANGER';
    if (zeroCount10 >= 2) return 'DANGER';
    if (currentStreak >= 4 && fastAltRate <= 0.25) return 'DANGER';

    // 2. TRANSITION Triggers ("Жёлтенький")
    if (currentStreak >= 3) return 'TRANSITION';
    if (zeroCount5 >= 1) return 'TRANSITION';
    if (fastAltRate < 0.60) return 'TRANSITION';
    if (streak3plusCount >= 2) return 'TRANSITION';

    // 3. ZEBRA Triggers
    if (currentStreak <= 2 && fastAltRate >= 0.60 && zeroCount5 === 0) {
      return 'ZEBRA';
    }

    return 'TRANSITION';
  }

  /**
   * Fast-adapting hysteresis filter:
   * - Instantly pivots into DANGER upon aggressive conditions.
   * - Smoothly and rapidly downshifts to TRANSITION as soon as a streak breaks.
   * - Re-enters ZEBRA without lingering in lockdown for 5-8 spins.
   */
  public static detectModeWithHysteresis(
    history: HistoryEntry[],
    prevMode: ServerMode,
    currMode: ServerMode,
    spinsSinceDangerExit: number,
    spinsInCurrentMode: number
  ): { mode: ServerMode; newPrevMode: ServerMode; newSpinsSinceDangerExit: number; newSpinsInCurrentMode: number } {
    const rawMode = this.detectMode(history);
    let newMode = rawMode;

    let newSpinsSinceDangerExit = spinsSinceDangerExit + 1;
    let newSpinsInCurrentMode = spinsInCurrentMode + 1;
    let newPrevMode = prevMode;

    // Responsive downshift:
    // If we were in DANGER, but rawMode indicates the streak broke or calm returned:
    // Immediately drop to TRANSITION to test the waters (no 3-spin forced lock).
    if (currMode === 'DANGER' && rawMode !== 'DANGER') {
      newMode = 'TRANSITION';
      newSpinsSinceDangerExit = 0;
    }

    // From TRANSITION to ZEBRA: requires 1 confirming clean spin (not 5!)
    if (currMode === 'TRANSITION' && rawMode === 'ZEBRA' && spinsSinceDangerExit < 1) {
      newMode = 'TRANSITION';
    }

    if (newMode !== currMode) {
      newPrevMode = currMode;
      newSpinsInCurrentMode = 1;
    }

    return {
      mode: newMode,
      newPrevMode,
      newSpinsSinceDangerExit,
      newSpinsInCurrentMode,
    };
  }

  /**
   * Zebra momentum detector (Follow vs Break).
   */
  public static getZebraMomentum(history: HistoryEntry[]): { followL1: boolean; confidence: number } {
    const nonZero = history.filter(h => h.outcome !== 'ZERO').slice(-6);
    if (nonZero.length < 4) return { followL1: true, confidence: 55 };

    let alternations = 0;
    for (let i = 1; i < nonZero.length; i++) {
      if (nonZero[i].outcome !== nonZero[i - 1].outcome) alternations++;
    }
    const altRate = alternations / (nonZero.length - 1);

    if (altRate >= 0.80) {
      return { followL1: false, confidence: 65 };
    } else if (altRate >= 0.60) {
      return { followL1: true, confidence: 55 };
    } else {
      return { followL1: true, confidence: 58 };
    }
  }

  /**
   * Micro-Pattern Detector (MPD) + Apex Matrix color recommender.
   */
  public static getRecommendationAndConfidence(history: HistoryEntry[]): PredictionResult {
    if (history.length === 0) return { recommendation: 'RED', confidence: 50, state: 'АНАЛИЗ' };

    const matrix = this.getApexMatrix(history);
    const nonZero = history.filter(h => h.outcome !== 'ZERO');

    let recommendation: Outcome = 'RED';
    let confidence = 50;
    let state = 'АНАЛИЗ';

    // === MICRO-PATTERN DETECTOR (MPD) ===
    if (nonZero.length >= 4) {
      const L1 = nonZero[nonZero.length - 1].outcome;
      const L2 = nonZero[nonZero.length - 2].outcome;
      const L3 = nonZero[nonZero.length - 3].outcome;
      const L4 = nonZero[nonZero.length - 4].outcome;

      // Echo Alternation A-B-A-B
      if (L1 === L3 && L2 === L4 && L1 !== L2) {
        recommendation = L1 === 'RED' ? 'BLACK' : 'RED';
        confidence = 82;
        state = 'ЭХО-ПАТТЕРН';
        return { recommendation, confidence, state };
      }

      // 3-Streak Break Wave (A-A-A after B)
      if (L1 === L2 && L2 === L3 && L4 !== L1) {
        recommendation = L1 === 'RED' ? 'BLACK' : 'RED';
        confidence = 78;
        state = 'ВОЛНА (СЛОМ СЕРИИ)';
        return { recommendation, confidence, state };
      }
    }

    if (nonZero.length < 2) {
      recommendation = nonZero.length > 0 ? nonZero[nonZero.length - 1].outcome : 'RED';
      return { recommendation, confidence, state };
    }

    const L1 = nonZero[nonZero.length - 1].outcome;
    const L2 = nonZero[nonZero.length - 2].outcome;

    const currentMaxStreak = matrix.currentActiveColor === 'RED' ? matrix.maxStreakRed : matrix.maxStreakBlack;

    // True Ceiling Bounce only applies to long mature runs (>= 5)
    if (matrix.currentActiveColor && matrix.currentActiveStreak >= Math.max(5, currentMaxStreak) && currentMaxStreak > 0) {
      recommendation = matrix.currentActiveColor === 'RED' ? 'BLACK' : 'RED';
      confidence = 90;
      state = 'ОТСКОК ОТ ПОТОЛКА';
    } else if (L1 === L2) {
      if (L1 === matrix.alpha && currentMaxStreak >= 3) {
        recommendation = L1;
        confidence = 75;
        state = 'АЛЬФА-ТРЕНД';
      } else if (L1 === matrix.omega) {
        recommendation = L1 === 'RED' ? 'BLACK' : 'RED';
        confidence = 30;
        state = 'ОМЕГА-ЛОВУШКА';
      } else {
        recommendation = L1 === 'RED' ? 'BLACK' : 'RED';
        confidence = 50;
        state = 'НЕЙТРАЛЬНО';
      }
    } else {
      const zebra = this.getZebraMomentum(history);
      if (zebra.followL1) {
        recommendation = L1;
      } else {
        recommendation = L1 === 'RED' ? 'BLACK' : 'RED';
      }
      confidence = zebra.confidence;
      state = zebra.followL1 ? 'ЧЕРЕДОВАНИЕ (FOLLOW)' : 'ЧЕРЕДОВАНИЕ (BREAK)';
    }

    if (L1 === matrix.alpha && L2 === matrix.omega) {
      let omegaStreakBefore = 0;
      for (let i = nonZero.length - 2; i >= 0; i--) {
        if (nonZero[i].outcome === matrix.omega) omegaStreakBefore++;
        else break;
      }
      if (omegaStreakBefore >= 2) {
        recommendation = matrix.alpha;
        confidence = 85;
        state = 'ЗАРОЖДЕНИЕ АЛЬФЫ';
      }
    }

    return { recommendation, confidence, state };
  }
}
