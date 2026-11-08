import { Outcome, PredictionResult, SpinRecord } from './types';

export class PrngDetector {
  /**
   * Calculate alternation rate (how frequently colors switch) over non-zero spins.
   */
  public static calcAlternationRate(records: SpinRecord[], windowSize: number = 15): number {
    const nonZero = records.filter(r => r.outcome !== 'ZERO').slice(-windowSize);
    if (nonZero.length < 2) return 0.5;
    let transitions = 0;
    for (let i = 1; i < nonZero.length; i++) {
      if (nonZero[i].outcome !== nonZero[i - 1].outcome) {
        transitions++;
      }
    }
    return transitions / (nonZero.length - 1);
  }

  /**
   * Calculate current active streak of the latest color.
   */
  public static calcCurrentStreak(records: SpinRecord[]): { color: Outcome | null; length: number } {
    if (records.length === 0) return { color: null, length: 0 };
    const lastColor = records[records.length - 1].outcome;
    if (lastColor === 'ZERO') return { color: 'ZERO', length: 1 };
    
    let length = 0;
    for (let i = records.length - 1; i >= 0; i--) {
      if (records[i].outcome === lastColor) {
        length++;
      } else {
        break;
      }
    }
    return { color: lastColor, length };
  }

  /**
   * CUSUM (Cumulative Sum Control Chart) to detect statistical regime shifts.
   * Compares recent win/loss stream against expected negative drift.
   */
  public static calcCusumState(records: SpinRecord[], windowSize: number = 30): {
    state: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
    scorePositive: number;
    scoreNegative: number;
  } {
    const recent = records.slice(-windowSize);
    if (recent.length < 5) {
      return { state: 'NEUTRAL', scorePositive: 0, scoreNegative: 0 };
    }

    const mu0 = -0.04; // Baseline expected return under -4.82% house edge
    const k = 0.20; // Slack parameter
    let sPos = 0;
    let sNeg = 0;

    for (const r of recent) {
      // Win = +1.0, Loss/Zero = -1.0
      const x = r.isWin ? 1.0 : -1.0;
      sPos = Math.max(0, sPos + (x - mu0 - k));
      sNeg = Math.max(0, sNeg - (x - mu0 + k));
    }

    const threshold = 2.5;
    if (sPos >= threshold && sPos > sNeg) {
      return { state: 'BULLISH', scorePositive: sPos, scoreNegative: sNeg };
    } else if (sNeg >= threshold && sNeg > sPos) {
      return { state: 'BEARISH', scorePositive: sPos, scoreNegative: sNeg };
    }
    return { state: 'NEUTRAL', scorePositive: sPos, scoreNegative: sNeg };
  }

  /**
   * Generate next color prediction using an ensemble of Micro-Pattern, Alternation, and Mean-Reversion filters.
   */
  public static predictNextOutcome(records: SpinRecord[]): PredictionResult {
    const defaultPrediction: PredictionResult = {
      recommendation: 'RED',
      confidence: 50,
      patternName: 'ИНИЦИАЛИЗАЦИЯ',
      rationale: 'Недостаточно данных для квантового анализа',
      alternationRate: 0.5,
      dominantColor: 'BALANCED',
      cusumState: 'NEUTRAL',
    };

    if (records.length === 0) return defaultPrediction;

    const nonZero = records.filter(r => r.outcome !== 'ZERO');
    const altRate = this.calcAlternationRate(records, 15);
    const { color: streakColor, length: streakLen } = this.calcCurrentStreak(records);
    const cusum = this.calcCusumState(records, 25);

    // Color distribution over last 20
    const last20 = nonZero.slice(-20);
    const redCount = last20.filter(r => r.outcome === 'RED').length;
    const blackCount = last20.length - redCount;
    let dominant: Outcome | 'BALANCED' = 'BALANCED';
    if (last20.length >= 10) {
      if (redCount / last20.length >= 0.65) dominant = 'RED';
      else if (blackCount / last20.length >= 0.65) dominant = 'BLACK';
    }

    if (nonZero.length < 3) {
      const lastColor = nonZero.length > 0 ? nonZero[nonZero.length - 1].outcome : 'RED';
      return {
        recommendation: lastColor,
        confidence: 52,
        patternName: 'БАЗОВЫЙ ИМПУЛЬС',
        rationale: 'Следование за последним цветом на старте сессии',
        alternationRate: altRate,
        dominantColor: dominant,
        cusumState: cusum.state,
      };
    }

    const L1 = nonZero[nonZero.length - 1].outcome;
    const L2 = nonZero[nonZero.length - 2].outcome;
    const L3 = nonZero[nonZero.length - 3].outcome;
    const oppL1: Outcome = L1 === 'RED' ? 'BLACK' : 'RED';

    // 1. High-Alternation Zebra Wave (Transitions >= 70%)
    if (altRate >= 0.70) {
      return {
        recommendation: oppL1,
        confidence: Math.round(55 + altRate * 20),
        patternName: 'ЗЕБРА-ВОЛНА (РЕЖИМ ЧЕРЕДОВАНИЯ)',
        rationale: `Частота смены цветов ${(altRate * 100).toFixed(0)}%. Играем на продолжение чередования.`,
        alternationRate: altRate,
        dominantColor: dominant,
        cusumState: cusum.state,
      };
    }

    // 2. Micro-Pattern: 2-2 Block (Echo Pattern: A-A-B-B or A-B-A-B)
    if (nonZero.length >= 4) {
      const L4 = nonZero[nonZero.length - 4].outcome;
      // Echo A-B-A-B
      if (L1 === L3 && L2 === L4 && L1 !== L2) {
        return {
          recommendation: oppL1,
          confidence: 68,
          patternName: 'ГАРМОНИЧЕСКИЙ ЭХО-ПАТТЕРН',
          rationale: 'Зафиксирован цикличный осциллятор исходов 1-1-1-1.',
          alternationRate: altRate,
          dominantColor: dominant,
          cusumState: cusum.state,
        };
      }
      // Block A-A-B-B
      if (L1 === L2 && L3 === L4 && L1 !== L3) {
        return {
          recommendation: oppL1,
          confidence: 64,
          patternName: 'ПАРНЫЙ БЛОК (2x2)',
          rationale: 'Завершен второй шаг дуплета. Вход в разворот блока.',
          alternationRate: altRate,
          dominantColor: dominant,
          cusumState: cusum.state,
        };
      }
    }

    // 3. Strik Parity Break (Streak length >= 4)
    if (streakLen >= 4 && streakColor !== 'ZERO') {
      return {
        recommendation: oppL1,
        confidence: Math.min(75, 54 + streakLen * 3),
        patternName: 'ДИСПЕРСИОННЫЙ РАЗВОРОТ СТРИКА',
        rationale: `Длина одноцветной серии ${streakLen}. Смещение дисперсии в пользу возврата к среднему.`,
        alternationRate: altRate,
        dominantColor: dominant,
        cusumState: cusum.state,
      };
    }

    // 4. Alpha Trend Momentum
    if (dominant !== 'BALANCED' && L1 === dominant) {
      return {
        recommendation: dominant,
        confidence: 62,
        patternName: 'АЛЬФА-ТРЕНД (ИМПУЛЬС ДОМИНАНТА)',
        rationale: `Доминирующий цвет ${dominant} (${((dominant === 'RED' ? redCount : blackCount) / last20.length * 100).toFixed(0)}%). Следование тренду.`,
        alternationRate: altRate,
        dominantColor: dominant,
        cusumState: cusum.state,
      };
    }

    // 5. Default Momentum Follow
    return {
      recommendation: L1,
      confidence: 53,
      patternName: 'ЛОКАЛЬНЫЙ ИМПУЛЬС',
      rationale: 'Нейтральная фаза рынка. Следование за последним цветом.',
      alternationRate: altRate,
      dominantColor: dominant,
      cusumState: cusum.state,
    };
  }
}
