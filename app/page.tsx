'use client';

import React, { useState, useEffect, useCallback, useMemo, useSyncExternalStore } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  RotateCcw,
  Undo2,
  CheckCircle2,
  AlertTriangle,
  Download,
  Sliders,
  Zap,
  Shield,
  Sparkles,
  Pencil,
  Activity,
  TrendingUp,
  Target,
  Flame
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  type ChartOptions
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import {
  Outcome,
  ServerMode,
  StrategyProfile,
  HistoryEntry,
  SavedSession,
  SessionLogEntry,
  PrngDetector,
  RiskGuard,
  BankrollManager,
  GAME_RULES
} from '../lib/engine';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Audio Engine
let audioCtx: AudioContext | null = null;
const initAudio = () => {
  if (!audioCtx && typeof window !== 'undefined') {
    const AudioContextClass =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
};

const playTone = (freq: number, type: OscillatorType, duration: number, vol: number = 0.1) => {
  initAudio();
  if (!audioCtx) return;
  try {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(vol, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
  } catch {
    // Audio restricted before interaction
  }
};

const playClick = () => playTone(800, 'sine', 0.08, 0.04);
const playHapticClick = () => playTone(150, 'square', 0.05, 0.08);
const playHum = () => playTone(60, 'sawtooth', 0.65, 0.08);
const playAlert = () => {
  playTone(880, 'square', 0.14, 0.05);
  setTimeout(() => playTone(1100, 'square', 0.25, 0.05), 140);
};

const HistoryIcon = React.memo(function HistoryIcon({ entry }: { entry: HistoryEntry }) {
  const { outcome, isWin } = entry;
  return (
    <div className="relative flex-shrink-0 group">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-bold font-mono text-white border transition-transform group-hover:scale-110
          ${outcome === 'RED'
            ? 'bg-rose-600 border-rose-400/70 shadow-[0_0_10px_rgba(244,63,94,0.28)]'
            : outcome === 'BLACK'
            ? 'bg-neutral-900 border-neutral-600 shadow-[0_0_10px_rgba(0,0,0,0.65)]'
            : 'bg-emerald-600 border-emerald-400/70 shadow-[0_0_10px_rgba(16,185,129,0.3)]'
          }`}
        title={`${outcome === 'RED' ? 'Красное' : outcome === 'BLACK' ? 'Чёрное' : 'Зеро'} • ${entry.betAmount.toLocaleString('ru-RU')} ₽ (${isWin ? '+' : ''}${entry.netProfit.toLocaleString('ru-RU')} ₽)`}
      >
        {outcome === 'RED' ? 'К' : outcome === 'BLACK' ? 'Ч' : 'З'}
      </div>
      <span
        className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border border-[#0B0B0D] ${
          isWin ? 'bg-emerald-400' : 'bg-rose-500'
        }`}
      />
    </div>
  );
});

const emptySubscribe = () => () => {};

const PROFILE_LABELS: Record<StrategyProfile, { title: string; badgeClass: string }> = {
  APEX_IDEAL: {
    title: 'APEX OPT',
    badgeClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/35 hover:bg-emerald-500/25',
  },
  TURBO_HARVEST: {
    title: 'TURBO',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/35 hover:bg-amber-500/25',
  },
  SHIELD_CONSERVATIVE: {
    title: 'SHIELD',
    badgeClass: 'bg-zinc-200/10 text-zinc-200 border-zinc-400/35 hover:bg-zinc-200/20',
  },
};

export default function MatreshkaQuantum() {
  const isClient = useSyncExternalStore(emptySubscribe, () => true, () => false);

  const [initialBankroll, setInitialBankroll] = useState<number>(0);
  const [balanceCorrection, setBalanceCorrection] = useState<number>(0);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [attackStep, setAttackStep] = useState<number>(0);
  const [cdt, setCdt] = useState<number>(0);
  const [zeroInSequence, setZeroInSequence] = useState<number>(0);
  const [currentMode, setCurrentMode] = useState<ServerMode>('ZEBRA');
  const [previousMode, setPreviousMode] = useState<ServerMode>('ZEBRA');
  const [spinsSinceDangerExit, setSpinsSinceDangerExit] = useState<number>(999);
  const [spinsInCurrentMode, setSpinsInCurrentMode] = useState<number>(0);
  const [sequenceStartMode, setSequenceStartMode] = useState<ServerMode>('ZEBRA');
  const [sequenceTargetSteps, setSequenceTargetSteps] = useState<number | undefined>(undefined);
  const [strategyProfile, setStrategyProfile] = useState<StrategyProfile>('APEX_IDEAL');

  const [sessionStartTime, setSessionStartTime] = useState<number>(() => Date.now());
  const [now, setNow] = useState<number>(() => Date.now());
  const [savedSessions, setSavedSessions] = useState<SavedSession[]>([]);
  const [sessionLogs, setSessionLogs] = useState<SessionLogEntry[]>([]);

  // Controls & Modals
  const [setupVal, setSetupVal] = useState('3500000');
  const [manualBet, setManualBet] = useState<number | null>(null);
  const [manualColor, setManualColor] = useState<Outcome | null>(null);
  const [isEditingBet, setIsEditingBet] = useState(false);
  const [editBetValue, setEditBetValue] = useState('');
  const [isEditingBalance, setIsEditingBalance] = useState(false);
  const [editBalanceValue, setEditBalanceValue] = useState('');
  const [showSummary, setShowSummary] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);

  // Interval timer
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Restore State
  useEffect(() => {
    const saved = localStorage.getItem('matreshka_quantum_v12_state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.initialBankroll) setInitialBankroll(Math.floor(parsed.initialBankroll));
        if (parsed.balanceCorrection !== undefined) setBalanceCorrection(Math.round(parsed.balanceCorrection));
        if (parsed.history) setHistory(parsed.history);
        if (parsed.currentStep) setCurrentStep(parsed.currentStep);
        if (parsed.attackStep !== undefined) setAttackStep(parsed.attackStep);
        if (parsed.cdt !== undefined) setCdt(Math.floor(parsed.cdt));
        if (parsed.zeroInSequence !== undefined) setZeroInSequence(parsed.zeroInSequence);
        if (parsed.currentMode) setCurrentMode(parsed.currentMode);
        if (parsed.previousMode) setPreviousMode(parsed.previousMode);
        if (parsed.spinsSinceDangerExit !== undefined) setSpinsSinceDangerExit(parsed.spinsSinceDangerExit);
        if (parsed.spinsInCurrentMode !== undefined) setSpinsInCurrentMode(parsed.spinsInCurrentMode);
        if (parsed.sessionStartTime) setSessionStartTime(parsed.sessionStartTime);
        if (parsed.strategyProfile) setStrategyProfile(parsed.strategyProfile);
        if (parsed.sequenceStartMode) setSequenceStartMode(parsed.sequenceStartMode);
        if (parsed.sequenceTargetSteps !== undefined) setSequenceTargetSteps(parsed.sequenceTargetSteps);
      } catch (e) {
        console.error('Failed to parse saved state', e);
      }
    }
    const savedSess = localStorage.getItem('matreshka_quantum_sessions');
    if (savedSess) {
      try {
        setSavedSessions(JSON.parse(savedSess));
      } catch {}
    }
  }, []);

  // Save State
  useEffect(() => {
    if (isClient && initialBankroll > 0) {
      localStorage.setItem('matreshka_quantum_v12_state', JSON.stringify({
        initialBankroll,
        balanceCorrection,
        history,
        currentStep,
        attackStep,
        cdt,
        zeroInSequence,
        currentMode,
        previousMode,
        spinsSinceDangerExit,
        spinsInCurrentMode,
        sequenceStartMode,
        sequenceTargetSteps,
        sessionStartTime,
        strategyProfile
      }));
    }
  }, [
    isClient,
    initialBankroll,
    balanceCorrection,
    history,
    currentStep,
    attackStep,
    cdt,
    zeroInSequence,
    currentMode,
    previousMode,
    spinsSinceDangerExit,
    spinsInCurrentMode,
    sequenceStartMode,
    sequenceTargetSteps,
    sessionStartTime,
    strategyProfile
  ]);

  // Derived bankroll & profit
  const rawHistoryBankroll = useMemo(() => {
    return initialBankroll + history.reduce((acc, curr) => acc + curr.netProfit, 0);
  }, [initialBankroll, history]);

  const currentBankroll = rawHistoryBankroll + balanceCorrection;
  const profit = currentBankroll - initialBankroll;
  const sessionROI = initialBankroll > 0 ? (Math.trunc((profit / initialBankroll) * 10000) / 100).toFixed(2) : '0.00';

  const zeroCountLast10 = useMemo(() => {
    return history.slice(-10).filter(h => h.outcome === 'ZERO').length;
  }, [history]);

  // Engine Params & Prediction (v14.0 Saturation-Aware Alpha Engine + Streak Fading + Zero-Shock Guard)
  const cycleCapital = currentBankroll + cdt;
  const isZeroShock =
    strategyProfile !== 'SHIELD_CONSERVATIVE' &&
    BankrollManager.isZeroShockActive(zeroCountLast10, zeroInSequence);
  const isZebraLocked =
    cdt > 0 &&
    BankrollManager.shouldLockZebra(strategyProfile, cycleCapital, sequenceStartMode, isZeroShock);
  const effectiveMode: ServerMode = isZebraLocked ? 'ZEBRA' : currentMode;

  const engineParams = useMemo(() => {
    return BankrollManager.getEngineParams(
      strategyProfile,
      effectiveMode,
      currentBankroll,
      cdt,
      cdt > 0 ? sequenceTargetSteps : undefined,
      isZeroShock,
      currentStep
    );
  }, [strategyProfile, effectiveMode, currentBankroll, cdt, sequenceTargetSteps, isZeroShock, currentStep]);

  const prevBetAmount = useMemo(() => {
    if (currentStep <= 1 || history.length === 0) return undefined;
    return history[history.length - 1]?.betAmount;
  }, [currentStep, history]);

  const nextCalculatedBet = useMemo(() => {
    return BankrollManager.calculateBet(
      cdt,
      currentStep,
      effectiveMode,
      engineParams,
      currentBankroll,
      prevBetAmount
    );
  }, [cdt, currentStep, effectiveMode, engineParams, currentBankroll, prevBetAmount]);

  const effectiveBet = manualBet !== null ? manualBet : nextCalculatedBet;
  const netWinIfHit = BankrollManager.calcNetWin(effectiveBet) - cdt;

  const prediction = useMemo(() => {
    return PrngDetector.getRecommendationAndConfidence(history);
  }, [history]);

  const recommendation = manualColor !== null ? manualColor : prediction.recommendation;
  const recommendationText = recommendation === 'RED' ? 'КРАСНОЕ' : recommendation === 'BLACK' ? 'ЧЁРНОЕ' : 'ЗЕРО';

  // Detailed Stats & Stream Analytics
  const detailedStats = useMemo(() => {
    return RiskGuard.computeDetailedStats(history, initialBankroll, sessionStartTime, now, balanceCorrection);
  }, [history, initialBankroll, sessionStartTime, now, balanceCorrection]);

  const apexMatrix = useMemo(() => PrngDetector.getApexMatrix(history), [history]);
  const globalSkew = useMemo(() => PrngDetector.getGlobalSkew(history), [history]);
  const localSkew = useMemo(() => PrngDetector.getLocalSkew(history), [history]);

  // Synchronized 15-spin Alpha strength (matches PrngDetector.getApexMatrix window=15 & localSkew)
  const alphaStrength15 = useMemo(() => {
    const nz15 = history.filter(h => h.outcome !== 'ZERO').slice(-15);
    if (nz15.length === 0) return { pct: 50, sample: 0 };
    const red15 = nz15.filter(h => h.outcome === 'RED').length;
    const domCount = Math.max(red15, nz15.length - red15);
    return { pct: Math.round((domCount / nz15.length) * 100), sample: nz15.length };
  }, [history]);

  const avgSpinPaceSec = useMemo(() => {
    if (sessionLogs.length <= 1) return 0;
    const slice = sessionLogs.slice(-10);
    let totalMs = 0;
    let cnt = 0;
    for (let i = 1; i < slice.length; i++) {
      if (slice[i].time_since_last_spin > 0) {
        totalMs += slice[i].time_since_last_spin;
        cnt++;
      }
    }
    return cnt > 0 ? Math.round(totalMs / cnt / 1000) : 0;
  }, [sessionLogs]);

  // Outcome Handler
  const handleOutcome = useCallback((outcome: Outcome) => {
    playHapticClick();
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);
    setIsEditingBalance(false);

    let isWin = false;
    let netProfit = 0;
    let nextStep = currentStep;
    let nextAttackStep = attackStep;
    let nextCdt = cdt;
    let nextZeroInSeq = zeroInSequence;

    if (outcome === 'ZERO') {
      isWin = false;
      netProfit = -effectiveBet;
      nextCdt += effectiveBet;
      nextStep = currentStep + 1;
      nextZeroInSeq++;
    } else if (recommendation === outcome) {
      isWin = true;
      netProfit = BankrollManager.calcNetWin(effectiveBet);
      nextCdt = Math.max(0, nextCdt - netProfit);

      if (nextCdt === 0) {
        nextStep = 1;
        nextAttackStep = 0;
        nextZeroInSeq = 0;
      }
    } else {
      isWin = false;
      netProfit = -effectiveBet;
      nextCdt += effectiveBet;
      nextStep = currentStep + 1;
    }

    const newEntry: HistoryEntry = {
      id: `${history.length}-${outcome}-${Date.now()}`,
      outcome,
      betAmount: effectiveBet,
      betColor: recommendation,
      isWin,
      netProfit
    };

    const wasAtStart = cdt === 0 || currentStep === 1;
    const finalHistory = [...history, newEntry];

    let newMode: ServerMode;
    let newPrevMode: ServerMode;
    let newSpinsSinceDangerExit: number;
    let newSpinsInCurrentMode: number;

    if (BankrollManager.usesFastModeDetector(strategyProfile)) {
      newMode = PrngDetector.detectModeFast(finalHistory);
      newPrevMode = newMode !== currentMode ? currentMode : previousMode;
      newSpinsSinceDangerExit = 999;
      newSpinsInCurrentMode = newMode !== currentMode ? 1 : spinsInCurrentMode + 1;
    } else {
      const hyst = PrngDetector.detectModeWithHysteresis(
        finalHistory,
        previousMode,
        currentMode,
        spinsSinceDangerExit,
        spinsInCurrentMode
      );
      newMode = hyst.mode;
      newPrevMode = hyst.newPrevMode;
      newSpinsSinceDangerExit = hyst.newSpinsSinceDangerExit;
      newSpinsInCurrentMode = hyst.newSpinsInCurrentMode;
    }

    if (nextCdt === 0) {
      setSequenceStartMode(newMode);
      setSequenceTargetSteps(undefined);
    } else if (wasAtStart) {
      const startCfg = BankrollManager.getCalibratedLadderConfig(
        strategyProfile,
        currentMode,
        currentBankroll
      );
      setSequenceStartMode(currentMode);
      setSequenceTargetSteps(startCfg.targetSteps);
    } else {
      const nextZero10 = finalHistory.slice(-10).filter(h => h.outcome === 'ZERO').length;
      const nextZeroShock =
        strategyProfile !== 'SHIELD_CONSERVATIVE' &&
        BankrollManager.isZeroShockActive(nextZero10, nextZeroInSeq);
      if (nextZeroShock && nextStep >= 2) {
        const nextCycleCap = currentBankroll + netProfit + nextCdt;
        const expandedN = BankrollManager.getCalibratedLadderConfig(
          strategyProfile,
          newMode,
          nextCycleCap
        ).targetSteps;
        setSequenceTargetSteps(prev => Math.min(10, Math.max(prev ?? expandedN, expandedN)));
      }
    }

    if (effectiveBet >= GAME_RULES.MAX_BET) {
      playAlert();
    }

    setHistory(finalHistory);
    setCurrentStep(nextStep);
    setAttackStep(nextAttackStep);
    setCdt(nextCdt);
    setZeroInSequence(nextZeroInSeq);
    setCurrentMode(newMode);
    setPreviousMode(newPrevMode);
    setSpinsSinceDangerExit(newSpinsSinceDangerExit);
    setSpinsInCurrentMode(newSpinsInCurrentMode);

    const nowMs = Date.now();
    const timeSinceLast = sessionLogs.length > 0 ? nowMs - sessionLogs[sessionLogs.length - 1].timestamp : 0;

    const newLogEntry: SessionLogEntry = {
      timestamp: nowMs,
      input_result: outcome,
      recommended_action: recommendation,
      current_bet: effectiveBet,
      current_step: currentStep,
      current_balance: Math.floor(currentBankroll + netProfit),
      server_state_detected: prediction.state,
      time_since_last_spin: timeSinceLast,
      current_mode: effectiveMode,
      is_win: isWin,
      net_profit: netProfit
    };
    setSessionLogs([...sessionLogs, newLogEntry]);

    if (nextStep === 5) playHum();
    if (nextStep >= 6) playAlert();

    const newBankroll = currentBankroll + netProfit;
    if (newBankroll >= initialBankroll * 1.25 && !showSummary) {
      setShowSummary(true);
    }
  }, [
    effectiveBet,
    recommendation,
    currentStep,
    attackStep,
    cdt,
    zeroInSequence,
    history,
    previousMode,
    currentMode,
    effectiveMode,
    spinsSinceDangerExit,
    spinsInCurrentMode,
    sessionLogs,
    currentBankroll,
    prediction.state,
    initialBankroll,
    showSummary,
    strategyProfile
  ]);

  // Undo Handler
  const handleUndo = useCallback(() => {
    if (history.length === 0) return;
    playClick();
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);
    setIsEditingBalance(false);

    const newHistory = history.slice(0, -1);
    setHistory(newHistory);

    const newLogs = sessionLogs.slice(0, -1);
    setSessionLogs(newLogs);

    let step = 1;
    let aStep = 0;
    let cdtVal = 0;
    let zeroInSeqVal = 0;
    let runningNet = 0;
    let currentModeVal: ServerMode = 'ZEBRA';
    let prevModeVal: ServerMode = 'ZEBRA';
    let spinsSinceDangerExitVal = 999;
    let spinsInCurrentModeVal = 0;
    let seqStartVal: ServerMode = 'ZEBRA';
    let seqTargetStepsVal: number | undefined = undefined;
    const useFast = BankrollManager.usesFastModeDetector(strategyProfile);

    for (let i = 0; i < newHistory.length; i++) {
      const entry = newHistory[i];
      const wasAtStart = cdtVal === 0 || step === 1;
      const startModeThisSpin = currentModeVal;
      const startBankThisSpin = initialBankroll + balanceCorrection + runningNet;
      const currentHist = newHistory.slice(0, i);
      const rec = PrngDetector.getRecommendationAndConfidence(currentHist).recommendation;
      const isWin = (entry.outcome === rec && entry.outcome !== 'ZERO');

      runningNet += entry.netProfit;

      if (entry.outcome === 'ZERO') {
        cdtVal += entry.betAmount;
        step++;
        zeroInSeqVal++;
      } else if (isWin) {
        cdtVal = Math.max(0, cdtVal - BankrollManager.calcNetWin(entry.betAmount));
        if (cdtVal === 0) {
          step = 1;
          aStep = 0;
          zeroInSeqVal = 0;
        }
      } else {
        cdtVal += entry.betAmount;
        step++;
      }

      const currentHistWithEntry = newHistory.slice(0, i + 1);
      if (useFast) {
        const nextM = PrngDetector.detectModeFast(currentHistWithEntry);
        if (nextM !== currentModeVal) {
          prevModeVal = currentModeVal;
          spinsInCurrentModeVal = 1;
        } else {
          spinsInCurrentModeVal++;
        }
        currentModeVal = nextM;
        spinsSinceDangerExitVal = 999;
      } else {
        const hysteresisResult = PrngDetector.detectModeWithHysteresis(
          currentHistWithEntry,
          prevModeVal,
          currentModeVal,
          spinsSinceDangerExitVal,
          spinsInCurrentModeVal
        );
        currentModeVal = hysteresisResult.mode;
        prevModeVal = hysteresisResult.newPrevMode;
        spinsSinceDangerExitVal = hysteresisResult.newSpinsSinceDangerExit;
        spinsInCurrentModeVal = hysteresisResult.newSpinsInCurrentMode;
      }

      if (cdtVal === 0) {
        seqStartVal = currentModeVal;
        seqTargetStepsVal = undefined;
      } else if (wasAtStart) {
        seqStartVal = startModeThisSpin;
        seqTargetStepsVal = BankrollManager.getCalibratedLadderConfig(
          strategyProfile,
          startModeThisSpin,
          startBankThisSpin
        ).targetSteps;
      } else {
        const z10 = currentHistWithEntry.slice(-10).filter(h => h.outcome === 'ZERO').length;
        const zShock = useFast && BankrollManager.isZeroShockActive(z10, zeroInSeqVal);
        if (zShock && step >= 2) {
          const cycCap = initialBankroll + balanceCorrection + runningNet + cdtVal;
          const expN = BankrollManager.getCalibratedLadderConfig(strategyProfile, currentModeVal, cycCap).targetSteps;
          seqTargetStepsVal = Math.min(10, Math.max(seqTargetStepsVal ?? expN, expN));
        }
      }
    }

    setCurrentStep(step);
    setAttackStep(aStep);
    setCdt(cdtVal);
    setZeroInSequence(zeroInSeqVal);
    setCurrentMode(currentModeVal);
    setPreviousMode(prevModeVal);
    setSpinsSinceDangerExit(spinsSinceDangerExitVal);
    setSpinsInCurrentMode(spinsInCurrentModeVal);
    setSequenceStartMode(seqStartVal);
    setSequenceTargetSteps(seqTargetStepsVal);
  }, [history, sessionLogs, initialBankroll, balanceCorrection, strategyProfile]);

  // Keyboard Hotkeys
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;

      if (e.code === 'Numpad1' || e.code === 'Digit1' || e.key === 'r' || e.key === 'R' || e.key === 'к' || e.key === 'К') {
        e.preventDefault();
        handleOutcome('RED');
      } else if (e.code === 'Numpad2' || e.code === 'Digit2' || e.key === 'b' || e.key === 'B' || e.key === 'ч' || e.key === 'Ч') {
        e.preventDefault();
        handleOutcome('BLACK');
      } else if (e.code === 'Numpad0' || e.code === 'Digit0' || e.key === 'z' || e.key === 'Z' || e.key === 'я' || e.key === 'Я') {
        e.preventDefault();
        handleOutcome('ZERO');
      } else if (e.code === 'NumpadDecimal' || e.code === 'Backspace' || e.key === 'u' || e.key === 'U' || e.key === 'г' || e.key === 'Г') {
        e.preventDefault();
        handleUndo();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleOutcome, handleUndo]);

  const resetFullSessionState = useCallback(() => {
    setInitialBankroll(0);
    setBalanceCorrection(0);
    setHistory([]);
    setCurrentStep(1);
    setAttackStep(0);
    setCdt(0);
    setZeroInSequence(0);
    setCurrentMode('ZEBRA');
    setPreviousMode('ZEBRA');
    setSpinsSinceDangerExit(999);
    setSpinsInCurrentMode(0);
    setSequenceStartMode('ZEBRA');
    setSequenceTargetSteps(undefined);
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);
    setIsEditingBalance(false);
    localStorage.removeItem('matreshka_quantum_v12_state');
  }, []);

  // Save Session to LocalStorage
  const saveCurrentSession = useCallback(() => {
    if (history.length === 0) return;
    const durationMs = Date.now() - sessionStartTime;
    const zeroCount = history.filter(h => h.outcome === 'ZERO').length;
    const newSession: SavedSession = {
      id: Date.now().toString(),
      date: Date.now(),
      profit,
      durationMs,
      zeroCount,
      roi: initialBankroll > 0 ? (profit / initialBankroll) * 100 : 0
    };
    const updated = [newSession, ...savedSessions].slice(0, 10);
    setSavedSessions(updated);
    localStorage.setItem('matreshka_quantum_sessions', JSON.stringify(updated));
  }, [history, sessionStartTime, profit, initialBankroll, savedSessions]);

  // Export JSON logs
  const exportSessionLogs = useCallback(() => {
    const exportData = {
      metadata: {
        date: new Date(sessionStartTime).toISOString(),
        initialBankroll,
        currentBankroll,
        balanceCorrection,
        totalProfit: profit,
        maxDrawdown: detailedStats.maxDrawdown,
        durationMs: Math.max(0, now - sessionStartTime),
        strategyProfile
      },
      logs: sessionLogs
    };

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute('href', dataStr);
    downloadAnchorNode.setAttribute('download', `matreshka_session_${new Date(sessionStartTime).toISOString().split('T')[0]}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  }, [sessionStartTime, initialBankroll, currentBankroll, balanceCorrection, profit, detailedStats.maxDrawdown, now, strategyProfile, sessionLogs]);

  // Chart data (Pure Carbon Obsidian styling)
  const chartData = useMemo(() => {
    return {
      labels: sessionLogs.map((_, index) => index + 1),
      datasets: [
        {
          label: 'Баланс (₽)',
          data: sessionLogs.map(log => log.current_balance),
          borderColor: profit >= 0 ? '#10B981' : '#F43F5E',
          backgroundColor: profit >= 0 ? 'rgba(16, 185, 129, 0.08)' : 'rgba(244, 63, 94, 0.08)',
          borderWidth: 2,
          pointRadius: sessionLogs.map(log => (log.input_result === 'ZERO' ? 4.5 : 0)),
          pointBackgroundColor: sessionLogs.map(log => (log.input_result === 'ZERO' ? '#F59E0B' : 'transparent')),
          pointBorderColor: sessionLogs.map(log => (log.input_result === 'ZERO' ? '#0B0B0D' : 'transparent')),
          pointBorderWidth: 1.5,
          tension: 0.22,
          fill: true
        }
      ]
    };
  }, [sessionLogs, profit]);

  const chartOptions = useMemo<ChartOptions<'line'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#060607',
        borderColor: 'rgba(255,255,255,0.14)',
        borderWidth: 1,
        titleColor: '#A3A3A3',
        bodyColor: '#FAFAFA',
        padding: 10,
        callbacks: {
          title: (items) => (items[0] ? `Спин #${items[0].label}` : ''),
          label: (context) => {
            if (context.parsed.y !== null) {
              return ` ${new Intl.NumberFormat('ru-RU').format(context.parsed.y)} ₽`;
            }
            return '';
          }
        }
      }
    },
    scales: {
      x: { display: false },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: {
          color: '#737373',
          font: { size: 10, family: 'var(--font-mono)' },
          callback: (val) => new Intl.NumberFormat('ru-RU', { notation: 'compact' }).format(Number(val))
        }
      }
    }
  }), []);

  if (!isClient) return null;

  // Onboarding Screen (Pure Obsidian Black)
  if (initialBankroll === 0) {
    const parsedBankroll = Math.floor(Number(setupVal) || 0);
    const params = BankrollManager.getEngineParams(strategyProfile, 'ZEBRA', parsedBankroll);

    return (
      <div className="min-h-screen bg-[#030304] flex items-center justify-center p-4 font-sans text-neutral-100">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-md w-full bg-[#0B0B0D] border border-white/[0.08] p-7 rounded-3xl shadow-[0_24px_90px_rgba(0,0,0,0.85)]"
        >
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/[0.06]">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
                <Sparkles className="text-emerald-400" size={17} />
              </div>
              <div>
                <h1 className="font-[family-name:var(--font-display)] text-sm font-bold tracking-widest uppercase text-white">
                  MATRESHKA QUANTUM
                </h1>
                <p className="text-[11px] text-neutral-400">Обсидиановый терминал управления</p>
              </div>
            </div>
            <span className="text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 px-2.5 py-1 rounded-full border border-emerald-500/30">
              v14.0
            </span>
          </div>

          <div className="space-y-5">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-neutral-400 text-[11px] font-semibold uppercase tracking-wider">Стартовый баланс (₽)</label>
                <div className="flex gap-1.5">
                  {[1500000, 2500000, 3800000, 6500000].map(preset => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setSetupVal(String(preset))}
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-md border transition-colors cursor-pointer ${
                        Number(setupVal) === preset
                          ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                          : 'bg-[#060607] border-white/[0.08] text-neutral-400 hover:text-white'
                      }`}
                    >
                      {(preset / 1000000).toFixed(1).replace('.0', '')}M
                    </button>
                  ))}
                </div>
              </div>
              <input
                type="number"
                value={setupVal}
                onChange={e => setSetupVal(e.target.value)}
                className="w-full bg-[#050506] border border-white/[0.1] text-white text-3xl p-4 rounded-2xl focus:outline-none focus:border-emerald-500/70 transition-colors font-mono tabular-nums text-center font-bold"
                placeholder="3500000"
              />
            </div>

            <div>
              <label className="block text-neutral-400 text-[11px] font-semibold uppercase tracking-wider mb-2">Профиль стратегии</label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setStrategyProfile('APEX_IDEAL')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 cursor-pointer ${
                    strategyProfile === 'APEX_IDEAL'
                      ? 'bg-emerald-500/15 border-emerald-500/60 text-emerald-300 shadow-[0_0_24px_rgba(16,185,129,0.16)]'
                      : 'bg-[#060607] border-white/[0.07] text-neutral-400 hover:text-white hover:border-white/20'
                  }`}
                >
                  <Sparkles size={15} />
                  <span>APEX OPT</span>
                  <span className="text-[9px] font-mono text-neutral-400 font-normal">8–10 шагов</span>
                </button>

                <button
                  type="button"
                  onClick={() => setStrategyProfile('TURBO_HARVEST')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 cursor-pointer ${
                    strategyProfile === 'TURBO_HARVEST'
                      ? 'bg-amber-500/15 border-amber-500/60 text-amber-300 shadow-[0_0_24px_rgba(245,158,11,0.16)]'
                      : 'bg-[#060607] border-white/[0.07] text-neutral-400 hover:text-white hover:border-white/20'
                  }`}
                >
                  <Zap size={15} />
                  <span>TURBO</span>
                  <span className="text-[9px] font-mono text-neutral-400 font-normal">7–9 шагов</span>
                </button>

                <button
                  type="button"
                  onClick={() => setStrategyProfile('SHIELD_CONSERVATIVE')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 cursor-pointer ${
                    strategyProfile === 'SHIELD_CONSERVATIVE'
                      ? 'bg-zinc-200/15 border-zinc-300/60 text-white shadow-[0_0_24px_rgba(255,255,255,0.10)]'
                      : 'bg-[#060607] border-white/[0.07] text-neutral-400 hover:text-white hover:border-white/20'
                  }`}
                >
                  <Shield size={15} />
                  <span>SHIELD</span>
                  <span className="text-[9px] font-mono text-neutral-400 font-normal">10 шагов</span>
                </button>
              </div>
            </div>

            {parsedBankroll > 0 && (
              <div className="bg-[#060607] p-4 rounded-2xl border border-white/[0.07] text-xs space-y-2 font-mono tabular-nums">
                <div className="flex justify-between">
                  <span className="text-neutral-400 font-sans">База (1-й шаг Зебра):</span>
                  <span className="font-bold text-white">{Math.floor(params.baseBet).toLocaleString('ru-RU')} ₽</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400 font-sans">Финал ({params.stepsToLimit}-й шаг):</span>
                  <span className="font-bold text-amber-400">
                    {Math.floor(params.projectedTerminalBet ?? GAME_RULES.MAX_BET).toLocaleString('ru-RU')} ₽
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400 font-sans">Множитель роста X:</span>
                  <span className="font-bold text-emerald-400">{params.growthFactor.toFixed(3)}x</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400 font-sans">Запас шагов:</span>
                  <span className="font-bold text-neutral-200">{params.stepsToLimit} (дост. {params.durabilitySteps})</span>
                </div>
              </div>
            )}

            {strategyProfile === 'TURBO_HARVEST' && parsedBankroll > 0 && parsedBankroll < 3000000 && (
              <div className="bg-amber-950/35 border border-amber-500/35 rounded-xl p-2.5 text-[11px] text-amber-200 text-center">
                При банке ниже 3 000 000 ₽ на часовой дистанции безопаснее APEX OPT.
              </div>
            )}

            <button
              onClick={() => {
                const val = Math.floor(Number(setupVal));
                if (val > 0) {
                  setInitialBankroll(val);
                  setBalanceCorrection(0);
                  setHistory([]);
                  setCurrentStep(1);
                  setAttackStep(0);
                  setCdt(0);
                  setZeroInSequence(0);
                  setCurrentMode('ZEBRA');
                  setPreviousMode('ZEBRA');
                  setSpinsSinceDangerExit(999);
                  setSpinsInCurrentMode(0);
                  setSequenceStartMode('ZEBRA');
                  setSequenceTargetSteps(undefined);
                  setSessionStartTime(Date.now());
                }
              }}
              disabled={!setupVal || Number(setupVal) <= 0}
              className="w-full bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-black font-extrabold py-4 rounded-2xl uppercase tracking-widest disabled:opacity-50 transition-all shadow-[0_8px_30px_rgba(16,185,129,0.28)] text-sm cursor-pointer"
            >
              Запустить сессию v14.0
            </button>

            {savedSessions.length > 0 && (
              <div className="pt-4 border-t border-white/[0.06]">
                <h3 className="text-neutral-400 text-[10px] font-bold uppercase tracking-widest mb-2.5">Архив сессий</h3>
                <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1 scrollbar-hide">
                  {savedSessions.map((s, i) => (
                    <div key={s.id} className="bg-[#060607] border border-white/[0.06] rounded-xl px-3 py-2 flex justify-between items-center text-xs">
                      <div>
                        <div className="text-neutral-300 font-semibold">Сессия №{savedSessions.length - i}</div>
                        <div className="text-[10px] text-neutral-500 font-mono">{Math.round(s.durationMs / 60000)} мин · Зеро: {s.zeroCount}</div>
                      </div>
                      <div className={`font-mono font-bold tabular-nums ${s.profit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {s.profit >= 0 ? '+' : ''}{(s.profit >= 0 ? Math.floor(s.profit) : Math.trunc(s.profit)).toLocaleString('ru-RU')} ₽
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    );
  }

  const durationMs = now - sessionStartTime;
  const activeProfileMeta = PROFILE_LABELS[strategyProfile];
  const zeroDiffWarning = detailedStats.totalSpins >= 15 && detailedStats.zeroRateExact >= 6.0;

  return (
    <div className="min-h-screen bg-[#030304] text-neutral-100 font-sans selection:bg-emerald-500/30 pb-14">
      {/* Compact Pure Black Tactical Header */}
      <header className="border-b border-white/[0.07] bg-[#060607]/95 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-md md:max-w-4xl lg:max-w-6xl mx-auto px-4 py-3 flex flex-wrap justify-between items-center gap-3">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${effectiveMode === 'DANGER' ? 'bg-rose-500' : effectiveMode === 'TRANSITION' ? 'bg-amber-400' : 'bg-emerald-400'}`} />
              <span className="font-[family-name:var(--font-display)] text-[11px] font-bold tracking-widest text-neutral-300 uppercase">
                MATRESHKA QUANTUM
              </span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 px-1.5 py-0.5 rounded">v14.0</span>
              <span className="text-[11px] font-mono tabular-nums text-neutral-400 bg-[#0B0B0D] border border-white/[0.08] px-2 py-0.5 rounded-md">
                {Math.floor(durationMs / 60000).toString().padStart(2, '0')}:
                {Math.floor((durationMs % 60000) / 1000).toString().padStart(2, '0')}
              </span>
              <button
                onClick={() => setShowProfileModal(true)}
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border transition-colors cursor-pointer ${activeProfileMeta.badgeClass}`}
                title="Сменить профиль стратегии"
              >
                {activeProfileMeta.title}
              </button>
            </div>

            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <div className={`text-2xl font-mono font-extrabold tracking-tight tabular-nums ${profit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {profit >= 0 ? '+' : ''}{(profit >= 0 ? Math.floor(profit) : Math.trunc(profit)).toLocaleString('ru-RU')} ₽
                <span className="text-xs text-neutral-400 font-semibold ml-1.5 font-sans">({sessionROI}%)</span>
              </div>

              {isEditingBalance ? (
                <div className="flex items-center gap-1.5 bg-[#0B0B0D] border border-emerald-500/45 rounded-lg px-2 py-0.5">
                  <span className="text-[10px] text-neutral-400">В игре:</span>
                  <input
                    type="number"
                    value={editBalanceValue}
                    onChange={e => setEditBalanceValue(e.target.value)}
                    className="bg-transparent text-xs font-mono font-bold text-white w-24 focus:outline-none tabular-nums"
                    autoFocus
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        const val = Math.floor(Number(editBalanceValue));
                        if (!isNaN(val) && val >= 0) setBalanceCorrection(val - rawHistoryBankroll);
                        setIsEditingBalance(false);
                      } else if (e.key === 'Escape') {
                        setIsEditingBalance(false);
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      const val = Math.floor(Number(editBalanceValue));
                      if (!isNaN(val) && val >= 0) setBalanceCorrection(val - rawHistoryBankroll);
                      setIsEditingBalance(false);
                    }}
                    className="text-[10px] bg-emerald-600 hover:bg-emerald-500 text-black font-bold px-1.5 py-0.5 rounded cursor-pointer"
                  >
                    ОК
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setEditBalanceValue(Math.floor(currentBankroll).toString());
                    setIsEditingBalance(true);
                  }}
                  className="text-xs text-neutral-400 hover:text-white font-mono tabular-nums flex items-center gap-1.5 transition-colors cursor-pointer group"
                  title="Синхронизировать баланс с игровым"
                >
                  <span>Баланс:</span>
                  <strong className="text-neutral-100 group-hover:text-emerald-300 transition-colors">
                    {Math.floor(currentBankroll).toLocaleString('ru-RU')} ₽
                  </strong>
                  {balanceCorrection !== 0 && (
                    <span className="text-[10px] text-amber-400">({balanceCorrection > 0 ? '+' : ''}{balanceCorrection})</span>
                  )}
                  <Pencil size={11} className="text-neutral-500 group-hover:text-emerald-400 transition-colors" />
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowProfileModal(true)}
              className="text-neutral-400 hover:text-white transition-colors p-2.5 bg-[#0B0B0D] rounded-xl border border-white/[0.08] cursor-pointer"
              title="Настройки профиля"
            >
              <Sliders size={17} />
            </button>
            <button
              onClick={() => setShowResetConfirm(true)}
              className="text-neutral-400 hover:text-rose-400 transition-colors p-2.5 bg-[#0B0B0D] rounded-xl border border-white/[0.08] cursor-pointer"
              title="Завершить сессию"
            >
              <RotateCcw size={17} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-md md:max-w-4xl lg:max-w-6xl mx-auto p-4">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* LEFT COLUMN: Decision & Action Terminal */}
          <div className="lg:col-span-5 space-y-4">
            {/* Primary Signal Display Card */}
            <motion.div
              key={`${currentStep}-${effectiveMode}-${recommendation}`}
              initial={{ opacity: 0.92, scale: 0.99 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.16 }}
              className={`relative overflow-hidden rounded-3xl p-5 border flex flex-col items-center justify-center min-h-[256px] transition-all bg-[#0B0B0D] ${
                effectiveMode === 'DANGER'
                  ? 'border-rose-500/65 shadow-[0_0_45px_rgba(244,63,94,0.14)]'
                  : effectiveMode === 'TRANSITION'
                  ? 'border-amber-500/55 shadow-[0_0_40px_rgba(245,158,11,0.12)]'
                  : 'border-emerald-500/50 shadow-[0_0_40px_rgba(16,185,129,0.12)]'
              }`}
            >
              {/* Status Bar */}
              <div className="w-full flex justify-between items-center mb-3">
                <div className={`text-xs font-extrabold tracking-widest uppercase font-mono ${
                  currentStep <= 3 ? 'text-emerald-400' : currentStep <= 6 ? 'text-amber-400' : 'text-rose-400'
                }`}>
                  ШАГ {currentStep} / {engineParams.stepsToLimit}
                </div>

                <div className="flex items-center gap-1.5">
                  {isZeroShock && cdt > 0 && currentStep >= 2 && (
                    <span className="text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-300 border border-amber-500/40">
                      ZERO-SHIELD
                    </span>
                  )}
                  {isZebraLocked && (
                    <span className="text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/35">
                      LOCK ({currentMode})
                    </span>
                  )}
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md border ${
                    effectiveMode === 'DANGER'
                      ? 'bg-rose-500/15 text-rose-300 border-rose-500/40'
                      : effectiveMode === 'TRANSITION'
                      ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                      : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                  }`}>
                    {effectiveMode === 'DANGER' ? 'DANGER' : effectiveMode === 'TRANSITION' ? 'ПЕРЕХОД' : 'ZEBRA'}
                  </span>
                </div>
              </div>

              {/* Pattern State & Confidence */}
              <div className="text-[11px] font-semibold text-neutral-400 tracking-wider uppercase flex items-center gap-2">
                <span>{prediction.state}</span>
                <span className="text-neutral-600">•</span>
                <span className="text-emerald-400 font-mono">{prediction.confidence}%</span>
              </div>

              {/* Hero Color Prediction */}
              <div className={`font-[family-name:var(--font-display)] text-5xl sm:text-6xl font-black tracking-tight my-3 select-none ${
                recommendation === 'RED'
                  ? 'text-rose-500 drop-shadow-[0_0_24px_rgba(244,63,94,0.32)]'
                  : recommendation === 'BLACK'
                  ? 'text-white drop-shadow-[0_0_20px_rgba(255,255,255,0.14)]'
                  : 'text-emerald-400'
              }`}>
                {recommendationText}
              </div>

              {/* Bet Amount & Inline Edit */}
              <div className="flex items-center justify-center">
                {isEditingBet ? (
                  <div className="flex flex-col items-center gap-2.5 bg-[#060607] p-3.5 rounded-2xl border border-white/15">
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        value={editBetValue}
                        onChange={e => setEditBetValue(e.target.value)}
                        className="bg-black border border-white/15 rounded-xl px-3 py-1.5 text-xl font-mono text-center w-36 text-white focus:outline-none focus:border-emerald-500 tabular-nums"
                        autoFocus
                        onKeyDown={e => {
                          if (e.key === 'Enter') {
                            const val = parseInt(editBetValue, 10);
                            if (!isNaN(val) && val >= 1000) setManualBet(val);
                            setIsEditingBet(false);
                          } else if (e.key === 'Escape') {
                            setIsEditingBet(false);
                          }
                        }}
                      />
                      <span className="text-neutral-400 text-sm font-bold">₽</span>
                    </div>

                    <div className="flex gap-2 items-center">
                      <button
                        onClick={() => setManualColor('RED')}
                        className={`w-8 h-8 rounded-full bg-rose-600 border border-rose-400 ${manualColor === 'RED' ? 'ring-2 ring-white' : ''}`}
                        title="Красное"
                      />
                      <button
                        onClick={() => setManualColor('ZERO')}
                        className={`w-8 h-8 rounded-full bg-emerald-600 border border-emerald-400 ${manualColor === 'ZERO' ? 'ring-2 ring-white' : ''}`}
                        title="Зеро"
                      />
                      <button
                        onClick={() => setManualColor('BLACK')}
                        className={`w-8 h-8 rounded-full bg-neutral-900 border border-neutral-500 ${manualColor === 'BLACK' ? 'ring-2 ring-white' : ''}`}
                        title="Чёрное"
                      />
                      <button
                        onClick={() => {
                          const val = parseInt(editBetValue, 10);
                          if (!isNaN(val) && val >= 1000) setManualBet(val);
                          setIsEditingBet(false);
                        }}
                        className="ml-1 bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 rounded-xl text-xs font-bold uppercase text-black cursor-pointer"
                      >
                        ОК
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-3xl sm:text-4xl font-mono font-extrabold text-white tabular-nums tracking-tight">
                      {Math.floor(effectiveBet).toLocaleString('ru-RU')} ₽
                    </span>
                    <button
                      onClick={() => {
                        setEditBetValue(Math.floor(effectiveBet).toString());
                        setIsEditingBet(true);
                      }}
                      className="text-neutral-500 hover:text-emerald-400 transition-colors p-1.5 rounded-lg hover:bg-white/[0.05] cursor-pointer"
                      title="Изменить ставку или цвет"
                    >
                      <Pencil size={15} />
                    </button>
                  </div>
                )}
              </div>

              {/* Clean Live Ladder Info & Net Profit Preview */}
              <div className="mt-3 pt-3 w-full border-t border-white/[0.06] flex items-center justify-between text-[11px] font-mono text-neutral-400">
                <span>
                  База <strong className="text-neutral-200">{Math.floor(engineParams.baseBet).toLocaleString('ru-RU')}</strong> · {engineParams.growthFactor.toFixed(2)}x
                </span>
                <span>
                  Выигрыш даст:{' '}
                  <strong className={netWinIfHit >= 0 ? 'text-emerald-400' : 'text-amber-400'}>
                    {netWinIfHit >= 0 ? '+' : ''}{netWinIfHit.toLocaleString('ru-RU')} ₽
                  </strong>
                </span>
              </div>

              {effectiveBet >= GAME_RULES.MAX_BET && (
                <div className="mt-2.5 bg-rose-500/20 border border-rose-500/50 text-rose-200 text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest">
                  Предельная ставка стола (1 000 000 ₽)
                </div>
              )}
            </motion.div>

            {/* CDT & Live EV Speed Strip */}
            <div className="grid grid-cols-2 gap-3">
              <div className={`p-3.5 rounded-2xl border transition-colors bg-[#0B0B0D] ${
                cdt === 0 ? 'border-white/[0.07]' : 'border-rose-500/35 bg-rose-950/15'
              }`}>
                <div className="text-[10px] text-neutral-400 uppercase tracking-wider font-semibold">Дефицит серии (CDT)</div>
                <div className={`text-lg font-mono font-bold tabular-nums mt-0.5 ${cdt === 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {Math.floor(cdt).toLocaleString('ru-RU')} ₽
                </div>
              </div>
              <div className="p-3.5 rounded-2xl border border-white/[0.07] bg-[#0B0B0D] text-right">
                <div className="text-[10px] text-neutral-400 uppercase tracking-wider font-semibold">Скорость EV / час</div>
                <div className={`text-lg font-mono font-bold tabular-nums mt-0.5 ${detailedStats.profitPerHour >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {detailedStats.profitPerHour >= 0 ? '+' : ''}{Math.trunc(detailedStats.profitPerHour).toLocaleString('ru-RU')} ₽
                </div>
              </div>
            </div>

            {/* Rapid Input Controls */}
            <div className="bg-[#0B0B0D] border border-white/[0.07] rounded-2xl p-3.5 space-y-2.5">
              <div className="flex items-center justify-between text-[10px] text-neutral-400 font-mono px-0.5">
                <span className="uppercase tracking-wider font-sans font-semibold">Фиксация исхода</span>
                <span>Темп: <strong className="text-neutral-200">{avgSpinPaceSec} сек</strong></span>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => handleOutcome('RED')}
                  className="bg-gradient-to-b from-rose-600 to-rose-700 hover:from-rose-500 hover:to-rose-600 active:scale-[0.97] transition-all h-20 rounded-xl font-black text-base sm:text-lg tracking-wide shadow-[0_6px_20px_rgba(225,29,72,0.28)] border border-rose-400/30 flex flex-col items-center justify-center cursor-pointer"
                >
                  <span>КРАСНОЕ</span>
                  <span className="text-[10px] text-rose-200/80 font-mono font-medium mt-0.5">[1] / [R]</span>
                </button>

                <button
                  onClick={() => handleOutcome('ZERO')}
                  className="bg-gradient-to-b from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 active:scale-[0.97] transition-all h-20 rounded-xl font-black text-base sm:text-lg tracking-wide shadow-[0_6px_20px_rgba(16,185,129,0.25)] border border-emerald-400/30 flex flex-col items-center justify-center cursor-pointer"
                >
                  <span>ЗЕРО</span>
                  <span className="text-[10px] text-emerald-200/80 font-mono font-medium mt-0.5">[0] / [Z]</span>
                </button>

                <button
                  onClick={() => handleOutcome('BLACK')}
                  className="bg-gradient-to-b from-neutral-800 to-neutral-950 hover:from-neutral-700 hover:to-neutral-900 active:scale-[0.97] transition-all h-20 rounded-xl font-black text-base sm:text-lg tracking-wide border border-neutral-600/50 shadow-[0_6px_20px_rgba(0,0,0,0.6)] flex flex-col items-center justify-center cursor-pointer"
                >
                  <span>ЧЁРНОЕ</span>
                  <span className="text-[10px] text-neutral-400 font-mono font-medium mt-0.5">[2] / [B]</span>
                </button>
              </div>

              <button
                onClick={handleUndo}
                disabled={history.length === 0}
                className="w-full py-2.5 rounded-xl bg-[#060607] border border-white/[0.07] text-neutral-400 hover:text-white hover:border-white/15 active:scale-[0.99] transition-all flex items-center justify-center gap-2 disabled:opacity-35 disabled:pointer-events-none uppercase tracking-wider text-[11px] font-semibold cursor-pointer"
              >
                <Undo2 size={14} /> Отменить последний спин [Backspace]
              </button>
            </div>

            {/* Durability Meter */}
            <div className="bg-[#0B0B0D] rounded-2xl p-4 border border-white/[0.07]">
              <div className="flex justify-between items-center text-[10px] font-bold text-neutral-400 mb-2.5 tracking-wider uppercase font-mono">
                <span>Запас прочности: {currentStep} / {engineParams.stepsToLimit}</span>
                <span className={currentStep >= engineParams.stepsToLimit ? 'text-amber-400' : 'text-emerald-400'}>
                  {Math.max(0, engineParams.stepsToLimit - currentStep)} ш. до потолка
                </span>
              </div>
              <div className="flex gap-1.5 h-2.5">
                {Array.from({ length: Math.max(7, engineParams.stepsToLimit) }, (_, idx) => idx + 1).map(i => {
                  let bgColor = 'bg-neutral-800';
                  if (i <= currentStep) {
                    if (i <= Math.floor(engineParams.stepsToLimit * 0.4)) bgColor = 'bg-emerald-500';
                    else if (i <= Math.floor(engineParams.stepsToLimit * 0.7)) bgColor = 'bg-amber-400';
                    else if (i < engineParams.stepsToLimit) bgColor = 'bg-rose-500';
                    else bgColor = 'bg-amber-300';
                  }
                  return (
                    <div
                      key={i}
                      className={`flex-1 rounded-sm ${bgColor} transition-colors duration-200`}
                      title={`Шаг ${i} из ${engineParams.stepsToLimit}`}
                    />
                  );
                })}
              </div>
              {currentStep >= engineParams.stepsToLimit && (
                <div className="mt-2.5 bg-amber-500/15 border border-amber-500/35 rounded-xl p-2 text-center text-amber-200 text-[10px] font-semibold">
                  Терминальный шаг: ставка упёрлась в {Math.min(GAME_RULES.MAX_BET, Math.floor(currentBankroll)).toLocaleString('ru-RU')} ₽
                </div>
              )}
            </div>
          </div>

          {/* RIGHT COLUMN: High-Value Performance Metrics, Chart & Stream Intelligence */}
          <div className="lg:col-span-7 space-y-4">
            {/* Live Performance KPI Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="bg-[#0B0B0D] border border-white/[0.07] rounded-2xl p-3.5">
                <div className="flex items-center justify-between text-[10px] text-neutral-400 font-semibold uppercase tracking-wider">
                  <span>Винрейт</span>
                  <Target size={13} className="text-emerald-400" />
                </div>
                <div className={`text-xl font-mono font-extrabold tabular-nums mt-1 ${
                  detailedStats.winRate >= 50 ? 'text-emerald-400' : detailedStats.winRate >= 46 ? 'text-white' : 'text-amber-400'
                }`}>
                  {detailedStats.winRate}%
                </div>
                <div className="text-[10px] font-mono text-neutral-400 mt-1">
                  б/Zero: <span className="text-neutral-200">{detailedStats.nonZeroWinRate}%</span> · L20: <span className="text-neutral-200">{detailedStats.recentWinRate20}%</span>
                </div>
              </div>

              <div className="bg-[#0B0B0D] border border-white/[0.07] rounded-2xl p-3.5">
                <div className="flex items-center justify-between text-[10px] text-neutral-400 font-semibold uppercase tracking-wider">
                  <span>Спины и Шаг</span>
                  <Activity size={13} className="text-zinc-300" />
                </div>
                <div className="text-xl font-mono font-extrabold text-white tabular-nums mt-1">
                  {detailedStats.winCount}<span className="text-emerald-400 text-xs">W</span> / {detailedStats.lossCount}<span className="text-rose-400 text-xs">L</span>
                </div>
                <div className="text-[10px] font-mono text-neutral-400 mt-1">
                  Ср. закр: <span className="text-neutral-200">{detailedStats.avgCloseStep}</span> · Пик: <span className="text-amber-300">{detailedStats.maxStepReached}</span>
                </div>
              </div>

              <div className="bg-[#0B0B0D] border border-white/[0.07] rounded-2xl p-3.5">
                <div className="flex items-center justify-between text-[10px] text-neutral-400 font-semibold uppercase tracking-wider">
                  <span>Просадка</span>
                  <TrendingUp size={13} className="text-rose-400" />
                </div>
                <div className="text-xl font-mono font-extrabold text-rose-400 tabular-nums mt-1">
                  {detailedStats.maxDrawdown > 0 ? '-' : ''}{detailedStats.maxDrawdown.toLocaleString('ru-RU')}
                </div>
                <div className="text-[10px] font-mono text-neutral-400 mt-1 truncate">
                  {detailedStats.currentDrawdown === 0 ? (
                    <span className="text-emerald-400">На пике баланса</span>
                  ) : (
                    <span>Сейчас: <span className="text-rose-300">-{detailedStats.currentDrawdown.toLocaleString('ru-RU')} ₽</span></span>
                  )}
                </div>
              </div>

              <div className="bg-[#0B0B0D] border border-white/[0.07] rounded-2xl p-3.5">
                <div className="flex items-center justify-between text-[10px] text-neutral-400 font-semibold uppercase tracking-wider">
                  <span>Оборот</span>
                  <Flame size={13} className="text-amber-400" />
                </div>
                <div className="text-xl font-mono font-extrabold text-neutral-100 tabular-nums mt-1">
                  {new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 2 }).format(detailedStats.totalWagered)}
                </div>
                <div className="text-[10px] font-mono text-neutral-400 mt-1">
                  На спин:{' '}
                  <span className={detailedStats.profitPerSpin >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                    {detailedStats.profitPerSpin >= 0 ? '+' : ''}{detailedStats.profitPerSpin.toLocaleString('ru-RU')} ₽
                  </span>
                </div>
              </div>
            </div>

            {/* Balance Chart */}
            <div className="bg-[#0B0B0D] border border-white/[0.07] rounded-2xl p-4">
              <div className="flex justify-between items-center mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-neutral-300 uppercase tracking-wider font-bold">Кривая баланса</span>
                  <span className="text-[10px] font-mono text-neutral-500">Пик: {Math.floor(detailedStats.peakBankroll).toLocaleString('ru-RU')} ₽</span>
                </div>
                <button
                  onClick={exportSessionLogs}
                  className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider uppercase px-2.5 py-1.5 rounded-lg bg-[#060607] border border-white/[0.08] hover:border-white/20 text-neutral-300 hover:text-white transition-colors cursor-pointer"
                >
                  <Download size={12} /> Экспорт JSON
                </button>
              </div>
              <div className="h-44 w-full">
                <Line data={chartData} options={chartOptions} />
              </div>
            </div>

            {/* Stream & Anomaly Intelligence */}
            <div className="bg-[#0B0B0D] border border-white/[0.07] rounded-2xl p-4 space-y-3.5">
              <div className="flex justify-between items-center pb-2.5 border-b border-white/[0.06]">
                <span className="text-[11px] text-neutral-300 uppercase tracking-wider font-bold">Монитор потока и аномалий</span>
                <div className="flex items-center gap-2 text-[10px] font-mono">
                  <span className="text-neutral-400">Зебра: <strong className="text-emerald-400">{detailedStats.zebraRatio}%</strong></span>
                  <span className="text-neutral-600">•</span>
                  <span className="text-neutral-400">
                    Текущая:{' '}
                    <strong className={
                      detailedStats.currentStreakColor === 'RED'
                        ? 'text-rose-400'
                        : detailedStats.currentStreakColor === 'ZERO'
                        ? 'text-emerald-400'
                        : 'text-white'
                    }>
                      {detailedStats.currentStreakColor === 'RED' ? 'К' : detailedStats.currentStreakColor === 'BLACK' ? 'Ч' : detailedStats.currentStreakColor === 'ZERO' ? 'З' : '-'} ×{detailedStats.currentStreakLength}
                    </strong>
                  </span>
                </div>
              </div>

              {/* Rolling Skew Progress Bar (Window 15, synchronized with Alpha) */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-[11px] font-mono">
                  <span className="text-rose-400 font-bold">Красное (15): {Math.round(localSkew.red)}%</span>
                  <span className="text-neutral-300 font-bold">Чёрное (15): {Math.round(localSkew.black)}%</span>
                </div>
                <div className="w-full h-2 rounded-full bg-neutral-800 overflow-hidden flex">
                  <div
                    className="h-full bg-rose-500 transition-all duration-300"
                    style={{ width: `${Math.round(localSkew.red)}%` }}
                  />
                  <div
                    className="h-full bg-neutral-400 transition-all duration-300"
                    style={{ width: `${Math.round(localSkew.black)}%` }}
                  />
                </div>
              </div>

              {/* Transparent Diagnostic Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-xs font-mono">
                <div className="bg-[#060607] border border-white/[0.06] rounded-xl p-2.5">
                  <div className="text-[9px] text-neutral-400 uppercase font-sans font-semibold mb-0.5">Альфа (окно 15)</div>
                  <div className={`font-bold flex items-center gap-1 ${
                    apexMatrix.alpha === 'RED' ? 'text-rose-400' : apexMatrix.alpha === 'BLACK' ? 'text-neutral-200' : 'text-neutral-400'
                  }`}>
                    <span>
                      {apexMatrix.alpha === 'RED'
                        ? `Красное · ${alphaStrength15.pct}%`
                        : apexMatrix.alpha === 'BLACK'
                        ? `Чёрное · ${alphaStrength15.pct}%`
                        : `Нейтрально · ${alphaStrength15.pct}%`}
                    </span>
                    {alphaStrength15.pct >= 70 && (
                      <span className="text-[8px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 px-1 py-0.2 rounded">
                        НАСЫЩ
                      </span>
                    )}
                  </div>
                </div>

                <div className="bg-[#060607] border border-white/[0.06] rounded-xl p-2.5">
                  <div className="text-[9px] text-neutral-400 uppercase font-sans font-semibold mb-0.5">Частота Зеро</div>
                  <div className={`font-bold ${
                    zeroDiffWarning ? 'text-rose-400' : detailedStats.zeroRateExact > 4.5 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {detailedStats.zeroCount}/{detailedStats.totalSpins} ({detailedStats.zeroRateExact}%)
                  </div>
                </div>

                <div className="bg-[#060607] border border-white/[0.06] rounded-xl p-2.5">
                  <div className="text-[9px] text-neutral-400 uppercase font-sans font-semibold mb-0.5">Ср. шаг до Зеро</div>
                  <div className="font-bold text-neutral-200">{detailedStats.avgZeroFrequency}</div>
                </div>

                <div className="bg-[#060607] border border-white/[0.06] rounded-xl p-2.5">
                  <div className="text-[9px] text-neutral-400 uppercase font-sans font-semibold mb-0.5">Серии: Ср. / Макс</div>
                  <div className="font-bold text-neutral-200">
                    {apexMatrix.avgStreakRed.toFixed(1)}:{apexMatrix.avgStreakBlack.toFixed(1)} · {apexMatrix.maxStreakRed}:{apexMatrix.maxStreakBlack}
                  </div>
                </div>
              </div>
            </div>

            {/* Recent History Rail */}
            <div className="bg-[#0B0B0D] border border-white/[0.07] rounded-2xl p-4 space-y-2.5">
              <div className="flex items-center justify-between text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
                <span>Лента исходов (последние 30)</span>
                <span className="font-mono text-neutral-500">
                  К {detailedStats.redCount} · Ч {detailedStats.blackCount} · З {detailedStats.zeroCount}
                </span>
              </div>
              <div className="flex gap-2 overflow-x-auto py-1 scrollbar-hide">
                {history.length === 0 ? (
                  <span className="text-xs text-neutral-500 font-mono">Ожидание первого спина...</span>
                ) : (
                  history.slice(-30).map(h => <HistoryIcon key={h.id} entry={h} />)
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Profile Selector Modal */}
      <AnimatePresence>
        {showProfileModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.94, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-[#0B0B0D] border border-white/10 p-6 rounded-3xl max-w-sm w-full space-y-4 shadow-2xl"
            >
              <div className="flex justify-between items-center border-b border-white/[0.07] pb-3">
                <h3 className="font-[family-name:var(--font-display)] font-bold text-xs uppercase tracking-widest text-white">Профиль стратегии · v14.0</h3>
                <button onClick={() => setShowProfileModal(false)} className="text-neutral-400 hover:text-white cursor-pointer">✕</button>
              </div>

              <div className="space-y-2.5">
                {(() => {
                  const zApex = BankrollManager.getCalibratedLadderConfig('APEX_IDEAL', 'ZEBRA', cycleCapital);
                  const tApex = BankrollManager.getCalibratedLadderConfig('APEX_IDEAL', 'TRANSITION', cycleCapital);
                  const dApex = BankrollManager.getCalibratedLadderConfig('APEX_IDEAL', 'DANGER', cycleCapital);
                  const zTurbo = BankrollManager.getCalibratedLadderConfig('TURBO_HARVEST', 'ZEBRA', cycleCapital);
                  const tTurbo = BankrollManager.getCalibratedLadderConfig('TURBO_HARVEST', 'TRANSITION', cycleCapital);
                  const dTurbo = BankrollManager.getCalibratedLadderConfig('TURBO_HARVEST', 'DANGER', cycleCapital);
                  const zShield = BankrollManager.getCalibratedLadderConfig('SHIELD_CONSERVATIVE', 'ZEBRA', cycleCapital);
                  const tShield = BankrollManager.getCalibratedLadderConfig('SHIELD_CONSERVATIVE', 'TRANSITION', cycleCapital);
                  const dShield = BankrollManager.getCalibratedLadderConfig('SHIELD_CONSERVATIVE', 'DANGER', cycleCapital);

                  return (
                    <>
                      <button
                        onClick={() => { setStrategyProfile('APEX_IDEAL'); setShowProfileModal(false); }}
                        className={`w-full p-3.5 rounded-2xl border text-left transition-all cursor-pointer ${
                          strategyProfile === 'APEX_IDEAL' ? 'bg-emerald-500/15 border-emerald-500/60 text-white' : 'bg-[#060607] border-white/[0.07] text-neutral-400 hover:border-white/20'
                        }`}
                      >
                        <div className="font-bold text-emerald-400 text-xs flex items-center gap-1.5 mb-1">
                          <Sparkles size={14} /> APEX OPT · Основной (Zero-Shield)
                        </div>
                        <div className="text-[11px] text-neutral-300 font-mono">
                          Z: {zApex.baseBet.toLocaleString('ru-RU')} ₽ ({zApex.targetSteps}ш) · T: {tApex.baseBet.toLocaleString('ru-RU')} ₽ ({tApex.targetSteps}ш) · D: {dApex.baseBet.toLocaleString('ru-RU')} ₽ ({dApex.targetSteps}ш)
                        </div>
                      </button>

                      <button
                        onClick={() => { setStrategyProfile('TURBO_HARVEST'); setShowProfileModal(false); }}
                        className={`w-full p-3.5 rounded-2xl border text-left transition-all cursor-pointer ${
                          strategyProfile === 'TURBO_HARVEST' ? 'bg-amber-500/15 border-amber-500/60 text-white' : 'bg-[#060607] border-white/[0.07] text-neutral-400 hover:border-white/20'
                        }`}
                      >
                        <div className="font-bold text-amber-400 text-xs flex items-center gap-1.5 mb-1">
                          <Zap size={14} /> TURBO · Агрессивный разгон
                        </div>
                        <div className="text-[11px] text-neutral-300 font-mono">
                          Z: {zTurbo.baseBet.toLocaleString('ru-RU')} ₽ ({zTurbo.targetSteps}ш) · T: {tTurbo.baseBet.toLocaleString('ru-RU')} ₽ ({tTurbo.targetSteps}ш) · D: {dTurbo.baseBet.toLocaleString('ru-RU')} ₽ ({dTurbo.targetSteps}ш)
                        </div>
                      </button>

                      <button
                        onClick={() => { setStrategyProfile('SHIELD_CONSERVATIVE'); setShowProfileModal(false); }}
                        className={`w-full p-3.5 rounded-2xl border text-left transition-all cursor-pointer ${
                          strategyProfile === 'SHIELD_CONSERVATIVE' ? 'bg-zinc-200/15 border-zinc-300/60 text-white' : 'bg-[#060607] border-white/[0.07] text-neutral-400 hover:border-white/20'
                        }`}
                      >
                        <div className="font-bold text-zinc-200 text-xs flex items-center gap-1.5 mb-1">
                          <Shield size={14} /> SHIELD · Максимальная броня
                        </div>
                        <div className="text-[11px] text-neutral-300 font-mono">
                          Z: {zShield.baseBet.toLocaleString('ru-RU')} ₽ ({zShield.targetSteps}ш) · T: {tShield.baseBet.toLocaleString('ru-RU')} ₽ ({tShield.targetSteps}ш) · D: {dShield.baseBet.toLocaleString('ru-RU')} ₽ ({dShield.targetSteps}ш)
                        </div>
                      </button>
                    </>
                  );
                })()}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Target Reached Modal */}
      <AnimatePresence>
        {showSummary && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.94, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-[#0B0B0D] border border-emerald-500/35 p-7 rounded-3xl max-w-sm w-full text-center shadow-[0_0_50px_rgba(16,185,129,0.18)]"
            >
              <div className="w-14 h-14 bg-emerald-500/15 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/30">
                <CheckCircle2 className="text-emerald-400" size={28} />
              </div>
              <h2 className="text-xl font-black tracking-tight mb-1 text-white">ЦЕЛЬ +25% ДОСТИГНУТА</h2>
              <p className="text-neutral-400 mb-5 text-xs">Отличный результат. Можно зафиксировать прибыль или продолжить сессию.</p>

              <div className="bg-[#060607] rounded-2xl p-4 mb-5 border border-white/[0.07] font-mono">
                <div className="text-[10px] text-neutral-400 uppercase tracking-widest mb-1 font-bold">ПРОФИТ СЕССИИ</div>
                <div className="text-3xl text-emerald-400 font-black tabular-nums">+{Math.floor(profit).toLocaleString('ru-RU')} ₽</div>
              </div>

              <div className="space-y-2">
                <button
                  onClick={() => {
                    saveCurrentSession();
                    exportSessionLogs();
                    setShowSummary(false);
                    resetFullSessionState();
                  }}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 text-black font-bold py-3.5 rounded-xl uppercase tracking-wider transition-colors text-xs cursor-pointer"
                >
                  Зафиксировать и выйти
                </button>
                <button
                  onClick={() => setShowSummary(false)}
                  className="w-full py-2.5 text-neutral-400 hover:text-white text-xs font-semibold uppercase tracking-wider transition-colors cursor-pointer"
                >
                  Продолжить игру
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Reset Confirmation Modal */}
      <AnimatePresence>
        {showResetConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.94, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-[#0B0B0D] border border-rose-500/35 p-7 rounded-3xl max-w-sm w-full text-center shadow-[0_0_50px_rgba(244,63,94,0.18)]"
            >
              <div className="w-14 h-14 bg-rose-500/15 rounded-full flex items-center justify-center mx-auto mb-4 border border-rose-500/30">
                <AlertTriangle className="text-rose-400" size={28} />
              </div>
              <h2 className="text-xl font-black tracking-tight mb-1 text-white">ЗАВЕРШИТЬ СЕССИЮ?</h2>
              <p className="text-neutral-400 mb-6 text-xs">Результаты и журнал спинов будут сохранены.</p>

              <div className="flex gap-2">
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="flex-1 py-3 rounded-xl border border-white/10 text-neutral-200 font-bold uppercase tracking-wider hover:bg-white/[0.05] transition-colors text-xs cursor-pointer"
                >
                  Отмена
                </button>
                <button
                  onClick={() => {
                    saveCurrentSession();
                    exportSessionLogs();
                    setShowResetConfirm(false);
                    resetFullSessionState();
                  }}
                  className="flex-1 bg-rose-600 hover:bg-rose-500 text-white font-bold py-3 rounded-xl uppercase tracking-wider transition-colors text-xs cursor-pointer"
                >
                  Завершить
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
