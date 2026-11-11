import { HistoryEntry } from './types';

export interface DetailedSessionStats {
  totalSpins: number;
  totalProfit: number;
  currentBankroll: number;
  roi: number;
  maxDrawdown: number;
  redCount: number;
  blackCount: number;
  zeroCount: number;
  redPct: number;
  blackPct: number;
  zeroPct: number;
  avgStreakLength: string;
  zebraRatio: number;
  avgZeroFrequency: string;
  profitPerHour: number;
  maxStreak: number;
  currentStreakLength: number;
  currentStreakColor: string | null;
}

export class RiskGuard {
  public static computeDetailedStats(
    history: HistoryEntry[],
    initialBankroll: number,
    sessionStartTime: number,
    now: number
  ): DetailedSessionStats {
    let currentBankroll = initialBankroll;
    let peak = initialBankroll;
    let maxDrawdown = 0;
    let redCount = 0;
    let blackCount = 0;
    let zeroCount = 0;

    let totalStreaks = 0;
    let totalStreakLength = 0;
    let colorChanges = 0;
    const zeroIntervals: number[] = [];
    let lastZeroIndex = -1;

    let currentStreakLen = 0;
    let currentStreakCol: string | null = null;
    let maxStreak = 0;
    let tempStreak = 0;
    let tempCol: string | null = null;

    for (let i = 0; i < history.length; i++) {
      const h = history[i];
      currentBankroll += h.netProfit >= 0 ? Math.floor(h.netProfit) : Math.trunc(h.netProfit);
      if (currentBankroll > peak) peak = currentBankroll;
      const dd = peak - currentBankroll;
      if (dd > maxDrawdown) maxDrawdown = dd;

      if (h.outcome === 'RED') redCount++;
      else if (h.outcome === 'BLACK') blackCount++;
      else if (h.outcome === 'ZERO') zeroCount++;

      // Max Streak
      if (h.outcome === tempCol) {
        tempStreak++;
      } else {
        tempCol = h.outcome;
        tempStreak = 1;
      }
      if (tempStreak > maxStreak) maxStreak = tempStreak;

      // Intervals and streaks
      if (h.outcome === 'ZERO') {
        if (lastZeroIndex !== -1) {
          zeroIntervals.push(i - lastZeroIndex);
        }
        lastZeroIndex = i;
        if (currentStreakLen > 0) {
          totalStreaks++;
          totalStreakLength += currentStreakLen;
        }
        currentStreakLen = 0;
        currentStreakCol = null;
      } else {
        if (h.outcome === currentStreakCol) {
          currentStreakLen++;
        } else {
          if (currentStreakLen > 0) {
            totalStreaks++;
            totalStreakLength += currentStreakLen;
            colorChanges++;
          }
          currentStreakCol = h.outcome;
          currentStreakLen = 1;
        }
      }
    }

    if (currentStreakLen > 0) {
      totalStreaks++;
      totalStreakLength += currentStreakLen;
    }

    const totalSpins = history.length;
    const totalProfit = Math.trunc(currentBankroll - initialBankroll);
    const roi = initialBankroll > 0 ? Math.trunc((totalProfit / initialBankroll) * 10000) / 100 : 0;
    const redPct = totalSpins > 0 ? Math.round((redCount / totalSpins) * 100) : 0;
    const blackPct = totalSpins > 0 ? Math.round((blackCount / totalSpins) * 100) : 0;
    const zeroPct = totalSpins > 0 ? Math.round((zeroCount / totalSpins) * 100) : 0;

    const avgStreakLength = totalStreaks > 0 ? (totalStreakLength / totalStreaks).toFixed(2) : '0.00';
    const zebraRatio = totalSpins > 1 ? Math.round((colorChanges / (totalSpins - 1)) * 100) : 0;
    const avgZeroFrequency = zeroIntervals.length > 0
      ? (zeroIntervals.reduce((a, b) => a + b, 0) / zeroIntervals.length).toFixed(1)
      : 'Ожид. ~25 (2/50)';

    const durationMs = Math.max(1000, now - sessionStartTime);
    const profitPerHour = durationMs > 0 ? Math.trunc(totalProfit / (durationMs / 3600000)) : 0;

    let currentStreakColor: string | null = null;
    let currentStreakLength = 0;
    if (history.length > 0) {
      currentStreakColor = history[history.length - 1].outcome;
      for (let i = history.length - 1; i >= 0; i--) {
        if (history[i].outcome === currentStreakColor) {
          currentStreakLength++;
        } else {
          break;
        }
      }
    }

    return {
      totalSpins,
      totalProfit,
      currentBankroll,
      roi,
      maxDrawdown,
      redCount,
      blackCount,
      zeroCount,
      redPct,
      blackPct,
      zeroPct,
      avgStreakLength,
      zebraRatio,
      avgZeroFrequency,
      profitPerHour,
      maxStreak,
      currentStreakLength,
      currentStreakColor,
    };
  }
}
