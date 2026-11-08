export type Outcome = 'RED' | 'BLACK' | 'ZERO';

export type ServerMode = 'ZEBRA' | 'TRANSITION' | 'DANGER';

export type StrategyProfile = 'APEX_IDEAL' | 'TURBO_HARVEST' | 'SHIELD_CONSERVATIVE';

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
}

export interface PredictionResult {
  recommendation: Outcome;
  confidence: number;
  state: string;
}
