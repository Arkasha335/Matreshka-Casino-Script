import { HistoryEntry } from './types';

export interface DetailedSessionStats {
  totalSpins: number;
  winCount: number;
  lossCount: number;
  winRate: number;
  nonZeroWinRate: number;
  recentWinRate20: number;
  recentWins20: number;
  recentCount20: number;
  totalWagered: number;
  avgCloseStep: string;
  maxStepReached: number;
  totalProfit: number;
  currentBankroll: number;
  peakBankroll: number;
  currentDrawdown: number;
  roi: number;
  maxDrawdown: number;
  redCount: number;
  blackCount: number;
  zeroCount: number;
  redPct: number;
  blackPct: number;
  zeroPct: number;
  zeroRateExact: number;
  avgStreakLength: string;
  zebraRatio: number;
  avgZeroFrequency: string;
  profitPerHour: number;
  profitPerSpin: number;
  maxStreak: number;
  currentStreakLength: number;
  currentStreakColor: string | null;
}

export class RiskGuard {
  public static computeDetailedStats(
    history: HistoryEntry[],
    initialBankroll: number,
    sessionStartTime: number,
    now: number,
    balanceCorrection: number = 0
  ): DetailedSessionStats {
    let currentBankroll = initialBankroll;
    let peak = initialBankroll;
    let maxDrawdown = 0;
    let redCount = 0;
    let blackCount = 0;
    let zeroCount = 0;
    let winCount = 0;
    let lossCount = 0;
    let totalWagered = 0;

    let simStep = 1;
    let simCdt = 0;
    let maxStepReached = history.length > 0 ? 1 : 0;
    const closeSteps: number[] = [];

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
      totalWagered += h.betAmount;
      currentBankroll += Math.round(h.netProfit);
      if (currentBankroll > peak) peak = currentBankroll;
      const dd = peak - currentBankroll;
      if (dd > maxDrawdown) maxDrawdown = dd;

      maxStepReached = Math.max(maxStepReached, simStep);
      if (h.isWin && h.outcome !== 'ZERO') {
        winCount++;
        simCdt = Math.max(0, simCdt - Math.round(h.netProfit));
        if (simCdt <= 0) {
          closeSteps.push(simStep);
          simCdt = 0;
          simStep = 1;
        }
      } else {
        lossCount++;
        simCdt += h.betAmount;
        simStep++;
      }

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

    currentBankroll += balanceCorrection;
    if (currentBankroll > peak) peak = currentBankroll;
    const currentDrawdown = Math.max(0, peak - currentBankroll);

    const totalSpins = history.length;
    const totalProfit = Math.trunc(currentBankroll - initialBankroll);
    const roi = initialBankroll > 0 ? Math.trunc((totalProfit / initialBankroll) * 10000) / 100 : 0;

    const winRate = totalSpins > 0 ? Number(((winCount / totalSpins) * 100).toFixed(1)) : 0;
    const nonZeroSpins = redCount + blackCount;
    const nonZeroWinRate = nonZeroSpins > 0 ? Number(((winCount / nonZeroSpins) * 100).toFixed(1)) : 0;

    const recentSlice = history.slice(-20);
    const recentCount20 = recentSlice.length;
    const recentWins20 = recentSlice.filter(h => h.isWin && h.outcome !== 'ZERO').length;
    const recentWinRate20 = recentCount20 > 0 ? Math.round((recentWins20 / recentCount20) * 100) : 0;

    const avgCloseStep = closeSteps.length > 0
      ? (closeSteps.reduce((a, b) => a + b, 0) / closeSteps.length).toFixed(1)
      : '—';

    const redPct = totalSpins > 0 ? Math.round((redCount / totalSpins) * 100) : 0;
    const blackPct = totalSpins > 0 ? Math.round((blackCount / totalSpins) * 100) : 0;
    const zeroPct = totalSpins > 0 ? Math.round((zeroCount / totalSpins) * 100) : 0;
    const zeroRateExact = totalSpins > 0 ? Number(((zeroCount / totalSpins) * 100).toFixed(1)) : 0;

    const avgStreakLength = totalStreaks > 0 ? (totalStreakLength / totalStreaks).toFixed(2) : '0.00';
    const zebraRatio = nonZeroSpins > 1 ? Math.round((colorChanges / (nonZeroSpins - 1)) * 100) : 0;
    const avgZeroFrequency = zeroIntervals.length > 0
      ? `${(zeroIntervals.reduce((a, b) => a + b, 0) / zeroIntervals.length).toFixed(1)} сп.`
      : '—';

    const durationMs = Math.max(1000, now - sessionStartTime);
    const profitPerHour = durationMs > 0 ? Math.trunc(totalProfit / (durationMs / 3600000)) : 0;
    const profitPerSpin = totalSpins > 0 ? Math.trunc(totalProfit / totalSpins) : 0;

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
      winCount,
      lossCount,
      winRate,
      nonZeroWinRate,
      recentWinRate20,
      recentWins20,
      recentCount20,
      totalWagered,
      avgCloseStep,
      maxStepReached,
      totalProfit,
      currentBankroll,
      peakBankroll: peak,
      currentDrawdown,
      roi,
      maxDrawdown,
      redCount,
      blackCount,
      zeroCount,
      redPct,
      blackPct,
      zeroPct,
      zeroRateExact,
      avgStreakLength,
      zebraRatio,
      avgZeroFrequency,
      profitPerHour,
      profitPerSpin,
      maxStreak,
      currentStreakLength,
      currentStreakColor,
    };
  }
}
