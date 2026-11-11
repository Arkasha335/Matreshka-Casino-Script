export type Outcome = 'RED' | 'BLACK' | 'ZERO';

export type ServerMode = 'ZEBRA' | 'TRANSITION' | 'DANGER';

export type StrategyProfile = 'APEX_IDEAL' | 'TURBO_HARVEST' | 'SHIELD_CONSERVATIVE';

export const GAME_RULES = {
  TOTAL_SLOTS: 50,
  RED_SLOTS: 24,
  BLACK_SLOTS: 24,
  ZERO_SLOTS: 2,
  MIN_BET: 1000,
  MAX_BET: 1000000,
  VIP_MAX_BET: 2000000,
  TAX_RATE: 0.02, // 2% commission on net win
  WIN_NET_RATIO: 0.98, // Net profit multiplier (bet * 0.98)
  EXPECTED_ZERO_INTERVAL: 25, // 50 / 2 = 25 spins
} as const;

export interface HistoryEntry {
  id: string;
  outcome: Outcome;
  betAmount: number;
  betColor: Outcome;
  isWin: boolean;
  netProfit: number;
}

export interface SavedSession {
  id: string;
  date: number;
  profit: number;
  durationMs: number;
  zeroCount: number;
  roi: number;
}

export interface SessionLogEntry {
  timestamp: number;
  input_result: Outcome;
  recommended_action: Outcome;
  current_bet: number;
  current_step: number;
  current_balance: number;
  server_state_detected: string;
  time_since_last_spin: number;
  current_mode: ServerMode;
  is_win: boolean;
  net_profit: number;
}

export interface ApexMatrix {
  alpha: Outcome | 'NEUTRAL';
  omega: Outcome | 'NEUTRAL';
  maxStreakRed: number;
  maxStreakBlack: number;
  currentActiveColor: Outcome | null;
  currentActiveStreak: number;
}

export interface SkewStats {
  red: number;
  black: number;
  dominant: Outcome | null;
}

export interface EngineParams {
  baseBet: number;
  step2Boost: number;
  step3Boost: number;
  growthFactor: number;
  sniperMult: number;
  stepsToLimit: number;
  durabilitySteps: number;
  tableLimit: number;
  projectedTerminalBet?: number;
}

export interface PredictionResult {
  recommendation: Outcome;
  confidence: number;
  state: string;
}
