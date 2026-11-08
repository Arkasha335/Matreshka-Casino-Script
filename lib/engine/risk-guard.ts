import { EngineSettings, SessionStats, SpinRecord } from './types';

export interface RiskStatus {
  isHalted: boolean;
  isZeroFreeze: boolean;
  freezeRemaining: number;
  reason: 'NONE' | 'STOP_LOSS_TRIPPED' | 'TAKE_PROFIT_LOCKED' | 'ZERO_FREEZE';
  message: string;
}

export class RiskGuard {
  /**
   * Evaluate session risk limits (Hard Stop-Loss, Trailing Take-Profit, Zero-Freeze).
   */
  public static evaluateRisk(
    records: SpinRecord[],
    settings: EngineSettings,
    currentBankroll: number
  ): RiskStatus {
    const { initialBankroll, stopLossPct, takeProfitPct, trailingStopPct, zeroFreezeSpins } = settings;

    // 1. Calculate Peak and Drawdown
    let peak = initialBankroll;
    let running = initialBankroll;
    for (const r of records) {
      running += r.netProfit;
      if (running > peak) {
        peak = running;
      }
    }
    // Also include current balance if higher
    if (currentBankroll > peak) {
      peak = currentBankroll;
    }

    const currentDrawdown = peak - currentBankroll;
    const maxAllowedDrawdown = initialBankroll * stopLossPct;

    // Hard Stop-Loss Check
    if (currentDrawdown >= maxAllowedDrawdown && records.length > 0) {
      return {
        isHalted: true,
        isZeroFreeze: false,
        freezeRemaining: 0,
        reason: 'STOP_LOSS_TRIPPED',
        message: `ЖЁСТКИЙ СТОП-ЛОСС: Просадка ${currentDrawdown.toLocaleString('ru-RU')} ₽ достигла лимита ${(stopLossPct * 100).toFixed(0)}%. Игра заблокирована для защиты капитала!`,
      };
    }

    // Trailing Take-Profit Check
    const currentProfit = currentBankroll - initialBankroll;
    const peakProfit = peak - initialBankroll;
    const takeProfitTarget = initialBankroll * takeProfitPct;

    if (peakProfit >= takeProfitTarget) {
      const trailingDrop = peakProfit - currentProfit;
      const allowedDrop = initialBankroll * trailingStopPct;
      if (trailingDrop >= allowedDrop) {
        return {
          isHalted: true,
          isZeroFreeze: false,
          freezeRemaining: 0,
          reason: 'TAKE_PROFIT_LOCKED',
          message: `ТРЕЙЛИНГ ТЕЙК-ПРОФИТ: Зафиксирована цель прибыли (+${peakProfit.toLocaleString('ru-RU')} ₽). Прибыль сохранена. Рекомендуется закрыть сессию.`,
        };
      }
    }

    // Zero-Freeze Check: Look back up to zeroFreezeSpins
    let freezeRemaining = 0;
    if (records.length > 0 && zeroFreezeSpins > 0) {
      for (let i = 0; i < Math.min(records.length, zeroFreezeSpins); i++) {
        const idx = records.length - 1 - i;
        if (records[idx].outcome === 'ZERO') {
          // Zero occurred (i + 1) spins ago
          const spinsSinceZero = i + 1;
          if (spinsSinceZero <= zeroFreezeSpins) {
            freezeRemaining = zeroFreezeSpins - spinsSinceZero + 1;
            break;
          }
        }
      }
    }

    if (freezeRemaining > 0) {
      return {
        isHalted: false,
        isZeroFreeze: true,
        freezeRemaining,
        reason: 'ZERO_FREEZE',
        message: `ZERO-FREEZE: Обнаружен сектор Зеро! Режим заморозки: пропустите еще ${freezeRemaining} спин(а) для исключения дуплета.`,
      };
    }

    return {
      isHalted: false,
      isZeroFreeze: false,
      freezeRemaining: 0,
      reason: 'NONE',
      message: 'Режим в норме. Риск-фильтры пройдены.',
    };
  }

  /**
   * Compute comprehensive session metrics.
   */
  public static computeSessionStats(
    records: SpinRecord[],
    initialBankroll: number,
    sessionStartTime: number,
    currentTime: number
  ): SessionStats {
    let currentBankroll = initialBankroll;
    let peak = initialBankroll;
    let maxDrawdown = 0;
    let wins = 0;
    let losses = 0;
    let zeros = 0;

    for (const r of records) {
      currentBankroll += r.netProfit;
      if (currentBankroll > peak) peak = currentBankroll;
      const dd = peak - currentBankroll;
      if (dd > maxDrawdown) maxDrawdown = dd;

      if (r.outcome === 'ZERO') zeros++;
      else if (r.isWin) wins++;
      else losses++;
    }

    const totalProfit = currentBankroll - initialBankroll;
    const roi = initialBankroll > 0 ? (totalProfit / initialBankroll) * 100 : 0;
    const maxDrawdownPct = initialBankroll > 0 ? (maxDrawdown / initialBankroll) * 100 : 0;
    const totalSpins = records.length;
    const winRate = (wins + losses) > 0 ? (wins / (wins + losses)) * 100 : 0;

    const durationMs = Math.max(1000, currentTime - sessionStartTime);
    const hours = durationMs / 3600000;
    const profitPerHour = hours > 0 ? totalProfit / hours : 0;

    return {
      initialBankroll,
      currentBankroll,
      totalProfit,
      roi,
      maxDrawdown,
      maxDrawdownPct,
      peakBankroll: peak,
      totalSpins,
      winCount: wins,
      lossCount: losses,
      zeroCount: zeros,
      winRate,
      profitPerHour,
      durationMs,
      status: 'ACTIVE',
    };
  }
}
