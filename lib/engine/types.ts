export type Outcome = 'RED' | 'BLACK' | 'ZERO';

export type ServerMode = 'HARVEST' | 'NEUTRAL' | 'DEFENSIVE' | 'FREEZE';

export type AggressionProfile = 'CONSERVATIVE_SHIELD' | 'BALANCED_QUANT' | 'HIGH_ROLLER_MAX';

export interface EngineSettings {
  initialBankroll: number;
  aggressionProfile: AggressionProfile;
  baseBetOverride: number | null;
  stopLossPct: number; // e.g. 0.15 for 15%
  takeProfitPct: number; // e.g. 0.25 for 25%
  trailingStopPct: number; // e.g. 0.04 for 4%
  zeroFreezeSpins: number; // e.g. 3 spins
  maxStepCap: number; // e.g. 4 steps before soft amortization
  surgeCompoundEnabled: boolean; // Wave riding on wins
}

export interface SpinRecord {
  id: string;
  timestamp: number;
  outcome: Outcome;
  recommendedColor: Outcome;
  betAmount: number;
  isWin: boolean;
  netProfit: number;
  balance: number;
  mode: ServerMode;
  step: number;
  cdt: number;
  surgeStep: number;
  confidence: number;
  pattern: string;
  isZeroFreeze: boolean;
  timeSinceLastSpin: number;
}

export interface PredictionResult {
  recommendation: Outcome;
  confidence: number;
  patternName: string;
  rationale: string;
  alternationRate: number;
  dominantColor: Outcome | 'BALANCED';
  cusumState: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
}

export interface BetCalculationResult {
  betAmount: number;
  step: number;
  surgeStep: number;
  mode: ServerMode;
  cdt: number;
  isFrozen: boolean;
  freezeRemaining: number;
  riskStatus: 'NORMAL' | 'SURGE_COMPOUND' | 'AMORTIZING' | 'STOP_LOSS_TRIPPED' | 'TAKE_PROFIT_LOCKED' | 'ZERO_FREEZE';
  riskMessage: string;
}

export interface SessionStats {
  initialBankroll: number;
  currentBankroll: number;
  totalProfit: number;
  roi: number;
  maxDrawdown: number;
  maxDrawdownPct: number;
  peakBankroll: number;
  totalSpins: number;
  winCount: number;
  lossCount: number;
  zeroCount: number;
  winRate: number;
  profitPerHour: number;
  durationMs: number;
  status: 'ACTIVE' | 'STOP_LOSS_TRIPPED' | 'TAKE_PROFIT_LOCKED' | 'ZERO_FREEZE';
}
