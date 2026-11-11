'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { RotateCcw, Undo2, CheckCircle2, AlertTriangle, Info, Download, Sliders, Zap, Shield, Sparkles } from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
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
  Legend
);

// Audio Engine
let audioCtx: AudioContext | null = null;
const initAudio = () => {
  if (!audioCtx && typeof window !== 'undefined') {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
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

const playClick = () => playTone(800, 'sine', 0.1, 0.05);
const playHapticClick = () => playTone(150, 'square', 0.05, 0.1);
const playHum = () => playTone(60, 'sawtooth', 0.8, 0.1);
const playAlert = () => {
  playTone(880, 'square', 0.15, 0.05);
  setTimeout(() => playTone(1100, 'square', 0.3, 0.05), 150);
};

const HistoryIcon = React.memo(function HistoryIcon({ outcome }: { outcome: Outcome }) {
  return (
    <div
      className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white border-2 transition-transform hover:scale-110 shadow-md
        ${outcome === 'RED' ? 'bg-red-600 border-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' :
        outcome === 'BLACK' ? 'bg-gray-900 border-gray-700 shadow-[0_0_8px_rgba(0,0,0,0.6)]' :
        'bg-emerald-600 border-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.6)]'}`}
    >
      {outcome === 'RED' ? 'К' : outcome === 'BLACK' ? 'Ч' : 'З'}
    </div>
  );
});

export default function MatreshkaQuantum() {
  const [isClient, setIsClient] = useState(false);
  const [initialBankroll, setInitialBankroll] = useState<number>(0);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [attackStep, setAttackStep] = useState<number>(0);
  const [cdt, setCdt] = useState<number>(0);
  const [currentMode, setCurrentMode] = useState<ServerMode>('ZEBRA');
  const [previousMode, setPreviousMode] = useState<ServerMode>('ZEBRA');
  const [spinsSinceDangerExit, setSpinsSinceDangerExit] = useState<number>(999);
  const [spinsInCurrentMode, setSpinsInCurrentMode] = useState<number>(0);
  const [sequenceStartMode, setSequenceStartMode] = useState<ServerMode>('ZEBRA');
  const [sequenceTargetSteps, setSequenceTargetSteps] = useState<number | undefined>(undefined);
  const [strategyProfile, setStrategyProfile] = useState<StrategyProfile>('APEX_IDEAL');
  const [tableLimit, setTableLimit] = useState<number>(GAME_RULES.VIP_MAX_BET);

  const [sessionStartTime, setSessionStartTime] = useState<number>(() => Date.now());
  const [now, setNow] = useState<number>(() => Date.now());
  const [savedSessions, setSavedSessions] = useState<SavedSession[]>([]);
  const [sessionLogs, setSessionLogs] = useState<SessionLogEntry[]>([]);

  // Controls & Modals
  const [setupVal, setSetupVal] = useState('1000000');
  const [manualBet, setManualBet] = useState<number | null>(null);
  const [manualColor, setManualColor] = useState<Outcome | null>(null);
  const [isEditingBet, setIsEditingBet] = useState(false);
  const [editBetValue, setEditBetValue] = useState('');
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
    setIsClient(true);
    const saved = localStorage.getItem('matreshka_quantum_v12_state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.initialBankroll) setInitialBankroll(parsed.initialBankroll);
        if (parsed.history) setHistory(parsed.history);
        if (parsed.currentStep) setCurrentStep(parsed.currentStep);
        if (parsed.attackStep !== undefined) setAttackStep(parsed.attackStep);
        if (parsed.cdt !== undefined) setCdt(parsed.cdt);
        if (parsed.currentMode) setCurrentMode(parsed.currentMode);
        if (parsed.previousMode) setPreviousMode(parsed.previousMode);
        if (parsed.spinsSinceDangerExit !== undefined) setSpinsSinceDangerExit(parsed.spinsSinceDangerExit);
        if (parsed.spinsInCurrentMode !== undefined) setSpinsInCurrentMode(parsed.spinsInCurrentMode);
        if (parsed.sessionStartTime) setSessionStartTime(parsed.sessionStartTime);
        if (parsed.strategyProfile) setStrategyProfile(parsed.strategyProfile);
        if (parsed.tableLimit) setTableLimit(parsed.tableLimit);
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
        history,
        currentStep,
        attackStep,
        cdt,
        currentMode,
        previousMode,
        spinsSinceDangerExit,
        spinsInCurrentMode,
        sequenceStartMode,
        sequenceTargetSteps,
        sessionStartTime,
        strategyProfile,
        tableLimit
      }));
    }
  }, [
    isClient,
    initialBankroll,
    history,
    currentStep,
    attackStep,
    cdt,
    currentMode,
    previousMode,
    spinsSinceDangerExit,
    spinsInCurrentMode,
    sequenceStartMode,
    sequenceTargetSteps,
    sessionStartTime,
    strategyProfile,
    tableLimit
  ]);

  // Derived current bankroll
  const currentBankroll = useMemo(() => {
    return initialBankroll + history.reduce((acc, curr) => acc + curr.netProfit, 0);
  }, [initialBankroll, history]);

  const profit = currentBankroll - initialBankroll;
  const sessionROI = initialBankroll > 0 ? ((profit / initialBankroll) * 100).toFixed(2) : '0.00';

  // Engine Params & Prediction
  const cycleCapital = currentBankroll + cdt;
  const isZebraLocked = cdt > 0 && BankrollManager.shouldLockZebra(strategyProfile, cycleCapital, sequenceStartMode);
  const effectiveMode: ServerMode = isZebraLocked ? 'ZEBRA' : currentMode;

  const engineParams = useMemo(() => {
    return BankrollManager.getEngineParams(
      strategyProfile,
      effectiveMode,
      currentBankroll,
      tableLimit,
      cdt,
      cdt > 0 ? sequenceTargetSteps : undefined
    );
  }, [strategyProfile, effectiveMode, currentBankroll, tableLimit, cdt, sequenceTargetSteps]);

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
      prevBetAmount,
      tableLimit
    );
  }, [cdt, currentStep, effectiveMode, engineParams, currentBankroll, prevBetAmount, tableLimit]);

  const effectiveBet = manualBet !== null ? manualBet : nextCalculatedBet;

  const prediction = useMemo(() => {
    return PrngDetector.getRecommendationAndConfidence(history);
  }, [history]);

  const recommendation = manualColor !== null ? manualColor : prediction.recommendation;
  const recommendationText = recommendation === 'RED' ? 'КРАСНОЕ' : recommendation === 'BLACK' ? 'ЧЁРНОЕ' : 'ЗЕРО';

  // Stats
  const detailedStats = useMemo(() => {
    return RiskGuard.computeDetailedStats(history, initialBankroll, sessionStartTime, now);
  }, [history, initialBankroll, sessionStartTime, now]);

  const apexMatrix = useMemo(() => PrngDetector.getApexMatrix(history), [history]);
  const globalSkew = useMemo(() => PrngDetector.getGlobalSkew(history), [history]);
  const localSkew = useMemo(() => PrngDetector.getLocalSkew(history), [history]);

  const nonZeroRecent = useMemo(() => history.filter(h => h.outcome !== 'ZERO').slice(-15), [history]);
  const altRateUI = useMemo(() => {
    if (nonZeroRecent.length < 2) return 0;
    let alt = 0;
    for (let i = 1; i < nonZeroRecent.length; i++) {
      if (nonZeroRecent[i].outcome !== nonZeroRecent[i - 1].outcome) alt++;
    }
    return Math.round((alt / (nonZeroRecent.length - 1)) * 100);
  }, [nonZeroRecent]);

  const zeroCountLast10 = useMemo(() => {
    return history.slice(-10).filter(h => h.outcome === 'ZERO').length;
  }, [history]);

  // Outcome Handler
  const handleOutcome = useCallback((outcome: Outcome) => {
    playHapticClick();
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);

    let isWin = false;
    let netProfit = 0;
    let nextStep = currentStep;
    let nextAttackStep = attackStep;
    let nextCdt = cdt;

    if (outcome === 'ZERO') {
      isWin = false;
      netProfit = -effectiveBet;
      nextCdt += effectiveBet;
      nextStep = currentStep + 1; // Zero increments step
    } else if (recommendation === outcome) {
      isWin = true;
      netProfit = Math.round(effectiveBet * GAME_RULES.WIN_NET_RATIO); // 2% casino tax
      nextCdt = Math.max(0, Math.round(nextCdt - netProfit));
      if (nextCdt < 10) nextCdt = 0;

      if (nextCdt === 0) {
        nextStep = 1;
        nextAttackStep = 0;
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
        currentBankroll,
        tableLimit
      );
      setSequenceStartMode(currentMode);
      setSequenceTargetSteps(startCfg.targetSteps);
    }

    if (effectiveBet >= tableLimit) {
      playAlert();
    }

    setHistory(finalHistory);
    setCurrentStep(nextStep);
    setAttackStep(nextAttackStep);
    setCdt(nextCdt);
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
      current_balance: Math.round(currentBankroll + netProfit),
      server_state_detected: prediction.state,
      time_since_last_spin: timeSinceLast,
      current_mode: effectiveMode,
      is_win: isWin,
      net_profit: netProfit
    };
    setSessionLogs([...sessionLogs, newLogEntry]);

    if (nextStep === 5) playHum();
    if (nextStep >= 6) playAlert();

    const newBankroll = initialBankroll + finalHistory.reduce((acc, curr) => acc + curr.netProfit, 0);
    if (newBankroll >= initialBankroll * 1.25 && !showSummary) {
      setShowSummary(true);
    }
  }, [
    effectiveBet,
    recommendation,
    currentStep,
    attackStep,
    cdt,
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
    strategyProfile,
    tableLimit
  ]);

  // Undo Handler
  const handleUndo = useCallback(() => {
    if (history.length === 0) return;
    playClick();
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);

    const newHistory = history.slice(0, -1);
    setHistory(newHistory);

    const newLogs = sessionLogs.slice(0, -1);
    setSessionLogs(newLogs);

    let step = 1;
    let aStep = 0;
    let cdtVal = 0;
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
      const startBankThisSpin = initialBankroll + runningNet;
      const currentHist = newHistory.slice(0, i);
      const rec = PrngDetector.getRecommendationAndConfidence(currentHist).recommendation;
      const isWin = (entry.outcome === rec && entry.outcome !== 'ZERO');

      runningNet += entry.netProfit;

      if (entry.outcome === 'ZERO') {
        cdtVal += entry.betAmount;
        step++;
      } else if (isWin) {
        cdtVal = Math.max(0, Math.round(cdtVal - Math.round(entry.betAmount * GAME_RULES.WIN_NET_RATIO)));
        if (cdtVal < 10) cdtVal = 0;
        if (cdtVal === 0) {
          step = 1;
          aStep = 0;
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
          startBankThisSpin,
          tableLimit
        ).targetSteps;
      }
    }

    setCurrentStep(step);
    setAttackStep(aStep);
    setCdt(cdtVal);
    setCurrentMode(currentModeVal);
    setPreviousMode(prevModeVal);
    setSpinsSinceDangerExit(spinsSinceDangerExitVal);
    setSpinsInCurrentMode(spinsInCurrentModeVal);
    setSequenceStartMode(seqStartVal);
    setSequenceTargetSteps(seqTargetStepsVal);
  }, [history, sessionLogs, initialBankroll, strategyProfile, tableLimit]);

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
        totalProfit: profit,
        maxDrawdown: detailedStats.maxDrawdown,
        durationMs: detailedStats.profitPerHour > 0 ? Math.round(now - sessionStartTime) : 0,
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
  }, [sessionStartTime, initialBankroll, currentBankroll, profit, detailedStats, now, strategyProfile, sessionLogs]);

  // Chart data
  const chartData = useMemo(() => {
    return {
      labels: sessionLogs.map((_, index) => index + 1),
      datasets: [
        {
          label: 'Баланс (₽)',
          data: sessionLogs.map(log => log.current_balance),
          borderColor: profit >= 0 ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)',
          backgroundColor: profit >= 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          pointRadius: sessionLogs.map(log => log.input_result === 'ZERO' ? 5 : 0),
          pointBackgroundColor: sessionLogs.map(log => log.input_result === 'ZERO' ? 'rgb(59, 130, 246)' : 'transparent'),
          pointBorderColor: sessionLogs.map(log => log.input_result === 'ZERO' ? 'rgb(59, 130, 246)' : 'transparent'),
          tension: 0.15,
          fill: true
        }
      ]
    };
  }, [sessionLogs, profit]);

  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context: { parsed: { y: number | null } }) => {
            if (context.parsed.y !== null) {
              return 'Баланс: ' + new Intl.NumberFormat('ru-RU').format(context.parsed.y) + ' ₽';
            }
            return '';
          }
        }
      }
    },
    scales: {
      x: { display: false },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.08)' },
        ticks: { color: 'rgba(255, 255, 255, 0.5)', font: { size: 10 } }
      }
    }
  }), []);

  if (!isClient) return null;

  // Onboarding Screen
  if (initialBankroll === 0) {
    const parsedBankroll = Number(setupVal) || 0;
    const params = BankrollManager.getEngineParams(strategyProfile, 'ZEBRA', parsedBankroll, tableLimit);
    const formatLimitShort = (lim: number) => `${(lim / 1000000).toFixed(lim % 1000000 === 0 ? 0 : 1)}М`;

    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4 font-sans text-white">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-md w-full bg-gray-900/90 border border-emerald-500/30 p-8 rounded-3xl shadow-[0_0_60px_rgba(16,185,129,0.15)]"
        >
          <div className="flex items-center justify-center gap-2 mb-2">
            <Sparkles className="text-emerald-400" size={20} />
            <h1 className="text-xl font-black text-white tracking-widest uppercase">MATRESHKA QUANTUM</h1>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-400 font-bold px-2 py-0.5 rounded border border-emerald-500/30">v12.5 SOLVER</span>
          </div>
          <p className="text-gray-400 text-center text-xs mb-3">
            50 слотов • 2 Зеро (4%) • Комиссия 2% • Точный решатель до {tableLimit.toLocaleString('ru-RU')} ₽
          </p>
          <div className="bg-black/40 border border-gray-800 rounded-xl p-2.5 mb-5 text-[11px] text-gray-400 text-center font-mono">
            Мин. ставка: <span className="text-white font-bold">1 000 ₽</span> • Потолок: <span className="text-emerald-400 font-bold">{formatLimitShort(tableLimit)} ₽</span> • {params.stepsToLimit} шагов
          </div>

          <div className="space-y-5">
            <div>
              <label className="block text-gray-400 text-[10px] font-bold uppercase tracking-widest mb-1.5">Ваш Баланс (₽)</label>
              <input
                type="number"
                value={setupVal}
                onChange={e => setSetupVal(e.target.value)}
                className="w-full bg-black/70 border border-gray-800 text-emerald-400 text-3xl p-4 rounded-2xl focus:outline-none focus:border-emerald-500 transition-colors font-mono text-center font-bold"
                placeholder="1000000"
              />
            </div>

            <div>
              <label className="block text-gray-400 text-[10px] font-bold uppercase tracking-widest mb-1.5">Лимит / Потолок Стола (₽)</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setTableLimit(GAME_RULES.MAX_BET)}
                  className={`py-2.5 px-3 rounded-xl border text-xs font-mono font-bold transition-all cursor-pointer ${
                    tableLimit === GAME_RULES.MAX_BET
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                      : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  1 000 000 ₽ <span className="block text-[9px] font-sans text-gray-400">Стандарт CRMP</span>
                </button>
                <button
                  type="button"
                  onClick={() => setTableLimit(GAME_RULES.VIP_MAX_BET)}
                  className={`py-2.5 px-3 rounded-xl border text-xs font-mono font-bold transition-all cursor-pointer ${
                    tableLimit === GAME_RULES.VIP_MAX_BET
                      ? 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-[0_0_15px_rgba(245,158,11,0.2)]'
                      : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  2 000 000 ₽ <span className="block text-[9px] font-sans text-gray-400">VIP / Максимальный EV</span>
                </button>
              </div>
            </div>

            <div>
              <label className="block text-gray-400 text-[10px] font-bold uppercase tracking-widest mb-2">Режим Калибровки Риска</label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setStrategyProfile('APEX_IDEAL')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 cursor-pointer ${
                    strategyProfile === 'APEX_IDEAL'
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.25)]'
                      : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  <Sparkles size={16} />
                  <span>APEX OPT</span>
                  <span className="text-[9px] font-mono text-gray-400">9-10 шагов</span>
                </button>

                <button
                  type="button"
                  onClick={() => setStrategyProfile('TURBO_HARVEST')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 cursor-pointer ${
                    strategyProfile === 'TURBO_HARVEST'
                      ? 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-[0_0_20px_rgba(245,158,11,0.25)]'
                      : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  <Zap size={16} />
                  <span>TURBO</span>
                  <span className="text-[9px] font-mono text-gray-400">8-9 шагов</span>
                </button>

                <button
                  type="button"
                  onClick={() => setStrategyProfile('SHIELD_CONSERVATIVE')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 cursor-pointer ${
                    strategyProfile === 'SHIELD_CONSERVATIVE'
                      ? 'bg-blue-500/20 border-blue-500 text-blue-300 shadow-[0_0_20px_rgba(59,130,246,0.25)]'
                      : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  <Shield size={16} />
                  <span>SHIELD</span>
                  <span className="text-[9px] font-mono text-gray-400">10 шагов</span>
                </button>
              </div>
            </div>

            {parsedBankroll > 0 && (
              <div className="bg-black/50 p-4 rounded-2xl border border-gray-800 text-xs text-gray-300 space-y-1.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-400">Базовая ставка (1-й шаг):</span>
                  <span className="font-bold text-white">{Math.round(params.baseBet).toLocaleString('ru-RU')} ₽</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Финальный шаг ({params.stepsToLimit}-й):</span>
                  <span className="font-bold text-amber-400">
                    {Math.round(params.projectedTerminalBet ?? tableLimit).toLocaleString('ru-RU')} ₽
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Множитель прогрессии (X):</span>
                  <span className="font-bold text-emerald-400">{params.growthFactor.toFixed(3)}x</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Прочность последовательности:</span>
                  <span className="font-bold text-white">{params.stepsToLimit} шагов (дост. {params.durabilitySteps})</span>
                </div>
              </div>
            )}

            {strategyProfile === 'TURBO_HARVEST' && parsedBankroll > 0 && parsedBankroll < 3000000 && (
              <div className="bg-amber-950/40 border border-amber-500/40 rounded-xl p-2.5 text-[11px] text-amber-200 text-center">
                Внимание: при банке ниже 3 000 000 ₽ режим TURBO (8 шагов) имеет повышенный риск проигрыша на часовой дистанции.
              </div>
            )}

            <button
              onClick={() => {
                const val = Number(setupVal);
                if (val > 0) {
                  setInitialBankroll(val);
                  setHistory([]);
                  setCurrentStep(1);
                  setAttackStep(0);
                  setCdt(0);
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
              className="w-full bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-black py-4 rounded-2xl uppercase tracking-widest disabled:opacity-50 transition-all shadow-[0_0_25px_rgba(16,185,129,0.3)] text-sm cursor-pointer"
            >
              Запустить Движок v12.5
            </button>

            {savedSessions.length > 0 && (
              <div className="mt-6 border-t border-gray-800 pt-4">
                <h3 className="text-gray-400 text-[10px] font-bold uppercase tracking-widest mb-3">Предыдущие сессии</h3>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-1 scrollbar-hide">
                  {savedSessions.map((s, i) => (
                    <div key={s.id} className="bg-black/50 border border-gray-800 rounded-xl p-2.5 flex justify-between items-center text-xs">
                      <div>
                        <div className="text-gray-400 font-bold">Сессия №{savedSessions.length - i}</div>
                        <div className="text-[10px] text-gray-500">{Math.round(s.durationMs / 60000)} мин | Зеро: {s.zeroCount}</div>
                      </div>
                      <div className={`font-mono font-bold ${s.profit >= 0 ? 'text-emerald-400' : 'text-red-500'}`}>
                        {s.profit >= 0 ? '+' : ''}{Math.round(s.profit).toLocaleString('ru-RU')} ₽
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

  return (
    <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-emerald-500/30 pb-16 transition-colors duration-500">
      {/* Header */}
      <header className="border-b border-gray-800 bg-[#050505]/90 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-md md:max-w-4xl lg:max-w-6xl mx-auto px-4 py-3 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <h1 className="text-[10px] font-bold tracking-widest text-gray-400 uppercase">MATRESHKA QUANTUM v12.5</h1>
              <span className="text-[10px] font-mono text-gray-400 bg-gray-900 border border-gray-800 px-1.5 py-0.5 rounded">
                {Math.floor(durationMs / 60000).toString().padStart(2, '0')}:
                {Math.floor((durationMs % 60000) / 1000).toString().padStart(2, '0')}
              </span>
            </div>
            <div className={`text-2xl font-mono font-black tracking-tight ${profit >= 0 ? 'text-emerald-400' : 'text-red-500'}`}>
              {profit >= 0 ? '+' : ''}{Math.round(profit).toLocaleString('ru-RU')} ₽
              <span className="text-xs text-gray-500 font-bold ml-1.5 font-sans">({sessionROI}%)</span>
            </div>
            <div className="text-[11px] text-gray-400 font-mono">
              Баланс: <span className="font-bold text-white">{Math.round(currentBankroll).toLocaleString('ru-RU')} ₽</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowProfileModal(true)}
              className="text-gray-400 hover:text-white transition-colors p-2.5 bg-gray-900 rounded-xl border border-gray-800"
              title="Выбор режима агрессии и потолка стола"
            >
              <Sliders size={18} />
            </button>
            <button
              onClick={() => setShowResetConfirm(true)}
              className="text-gray-400 hover:text-red-400 transition-colors p-2.5 bg-gray-900 rounded-xl border border-gray-800"
              title="Завершить сессию"
            >
              <RotateCcw size={18} />
            </button>
          </div>
        </div>
      </header>

      {/* Game Rules & Casino Table Context Strip */}
      <div className="bg-gray-950/80 border-b border-gray-800/80 py-1.5 px-4">
        <div className="max-w-md md:max-w-4xl lg:max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-gray-400">
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-bold">50 СЛОТОВ:</span>
            <span>24 Красных (48%)</span>
            <span className="text-gray-600">•</span>
            <span>24 Чёрных (48%)</span>
            <span className="text-gray-600">•</span>
            <span className="text-emerald-400 font-bold">2 Зеро (4.0%)</span>
          </div>
          <div className="flex items-center gap-2">
            <span>Мин: <strong className="text-white">1 000 ₽</strong></span>
            <span className="text-gray-600">•</span>
            <button
              onClick={() => setShowProfileModal(true)}
              className="hover:text-white transition-colors cursor-pointer"
              title="Изменить лимит стола"
            >
              Лимит: <strong className="text-amber-400">{tableLimit.toLocaleString('ru-RU')} ₽</strong>
            </button>
            <span className="text-gray-600">•</span>
            <span>Комиссия: <strong className="text-gray-300">2%</strong></span>
          </div>
        </div>
      </div>

      <main className="max-w-md md:max-w-4xl lg:max-w-6xl mx-auto p-4 space-y-4">
        <div className="md:grid md:grid-cols-2 md:gap-6 lg:gap-8 items-start space-y-4 md:space-y-0">
          {/* Left Column: Command & Play Area */}
          <div className="space-y-4">
        {/* Main Quantum Display Card */}
        <motion.div
          key={`${currentStep}-${effectiveMode}-${recommendation}`}
          initial={{ scale: 0.98, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={`relative overflow-hidden rounded-3xl p-6 border-2 flex flex-col items-center justify-center min-h-[250px] shadow-2xl transition-all
            ${effectiveMode === 'DANGER' ? 'bg-black border-red-500 shadow-[0_0_40px_rgba(239,68,68,0.3)] animate-pulse' :
            effectiveMode === 'TRANSITION' ? 'bg-black border-yellow-500 shadow-[0_0_35px_rgba(234,179,8,0.2)]' :
            'bg-black border-emerald-500 shadow-[0_0_35px_rgba(16,185,129,0.2)]'}`}
        >
          {/* Top Indicator Row */}
          <div className="w-full flex justify-between items-center mb-1">
            <div className={`text-xs font-black tracking-widest uppercase ${
              currentStep <= 3 ? 'text-emerald-400' : currentStep <= 6 ? 'text-yellow-400' : 'text-red-500'
            }`}>
              {effectiveMode === 'DANGER' ? `ШАГ: ${currentStep} (DANGER)` : `ШАГ ПРОГРЕССИИ: ${currentStep}`}
            </div>

            <div className="text-right flex items-center gap-1.5">
              {isZebraLocked && (
                <span className="text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/40">
                  LOCK ({currentMode})
                </span>
              )}
              <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded border ${
                effectiveMode === 'DANGER' ? 'bg-red-500/20 text-red-400 border-red-500/40' :
                effectiveMode === 'TRANSITION' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40' :
                'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
              }`}>
                {effectiveMode === 'DANGER' ? '🔴 DANGER (МОНО-СЕРИИ 5+ / ZERO)' :
                 effectiveMode === 'TRANSITION' ? '🟡 ПЕРЕХОДНЫЙ (СЕРИИ 3-4)' :
                 '🟢 ЧЕРЕДОВАНИЕ (ZEBRA)'}
              </span>
            </div>
          </div>

          {/* Subtitle / Pattern Info */}
          <div className="text-[11px] font-bold text-gray-400 tracking-wider uppercase mb-1 flex items-center gap-1.5">
            <span>{prediction.state}</span>
            <span className="text-gray-600">•</span>
            <span className="text-emerald-400 font-mono">{prediction.confidence}% уверенность</span>
          </div>

          {/* Mode Strategy Hint */}
          <div className="text-[10px] font-medium text-gray-400 text-center mb-1">
            {effectiveMode === 'ZEBRA' && `✨ Чередование: макс. сбор прибыли (B₀ ${Math.round(engineParams.baseBet).toLocaleString('ru-RU')} ₽) • ${engineParams.stepsToLimit} шагов • ${isZebraLocked ? 'Zebra Lock активен' : 'Высокий EV'}`}
            {effectiveMode === 'TRANSITION' && `⚡ Переходная зона: баланс профита/риска (B₀ ${Math.round(engineParams.baseBet).toLocaleString('ru-RU')} ₽) • ${engineParams.stepsToLimit} шагов`}
            {effectiveMode === 'DANGER' && `🛡️ Аномалии / Zero: защита банка (B₀ ${Math.round(engineParams.baseBet).toLocaleString('ru-RU')} ₽) • ${engineParams.stepsToLimit} шагов • Horizon Guard`}
          </div>

          {/* Dynamic Constant Multiplier Badge */}
          <div className="text-[10px] font-mono text-gray-400 bg-gray-900/80 border border-gray-800 px-2.5 py-0.5 rounded-full mb-1 flex items-center gap-1.5 shadow-sm">
            <span>Множитель X: <strong className="text-emerald-400 font-bold">{engineParams.growthFactor.toFixed(3)}x</strong></span>
            <span className="text-gray-600">•</span>
            <span>Потолок {Math.round(engineParams.projectedTerminalBet ?? tableLimit).toLocaleString('ru-RU')} ₽ на шаге {engineParams.stepsToLimit}</span>
          </div>

          {/* Next Recommendation in Large Display */}
          <div className={`text-6xl sm:text-7xl font-black tracking-tighter my-2 drop-shadow-md ${
            effectiveMode === 'DANGER' ? 'text-red-400' :
            recommendation === 'RED' ? 'text-red-500' :
            recommendation === 'BLACK' ? 'text-white' : 'text-emerald-400'
          }`}>
            {recommendationText}
          </div>

          {/* Bet Display with Misclick Edit Icon */}
          <div className="mt-1 flex items-center justify-center gap-3">
            {isEditingBet ? (
              <div className="flex flex-col items-center gap-3 bg-gray-900/90 p-4 rounded-2xl border border-gray-700">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400 text-sm font-bold">СТАВКА:</span>
                  <input
                    type="number"
                    value={editBetValue}
                    onChange={e => setEditBetValue(e.target.value)}
                    className="bg-black border border-gray-700 rounded-xl px-3 py-1 text-2xl font-mono text-center w-36 text-white focus:outline-none focus:border-emerald-500"
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
                  <span className="text-gray-400 text-sm font-bold">₽</span>
                </div>

                <div className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Изменить цвет (мисклик)</div>
                <div className="flex gap-2.5 items-center">
                  <button
                    onClick={() => setManualColor('RED')}
                    className={`w-10 h-10 rounded-full bg-red-600 border border-red-400 shadow-[0_0_12px_rgba(220,38,38,0.5)] ${manualColor === 'RED' ? 'ring-4 ring-white' : ''}`}
                    title="Выбрать Красное"
                  />
                  <button
                    onClick={() => setManualColor('ZERO')}
                    className={`w-10 h-10 rounded-full bg-emerald-600 border border-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.5)] ${manualColor === 'ZERO' ? 'ring-4 ring-white' : ''}`}
                    title="Выбрать Зеро"
                  />
                  <button
                    onClick={() => setManualColor('BLACK')}
                    className={`w-10 h-10 rounded-full bg-gray-800 border border-gray-600 shadow-[0_0_12px_rgba(0,0,0,0.5)] ${manualColor === 'BLACK' ? 'ring-4 ring-white' : ''}`}
                    title="Выбрать Чёрное"
                  />
                  <button
                    onClick={() => {
                      const val = parseInt(editBetValue, 10);
                      if (!isNaN(val) && val >= 1000) setManualBet(val);
                      setIsEditingBet(false);
                    }}
                    className="ml-2 bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 rounded-xl text-xs font-bold uppercase tracking-wider text-white transition-colors"
                  >
                    ОК
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-3xl sm:text-4xl font-mono font-black text-white">
                  {Math.round(effectiveBet).toLocaleString('ru-RU')} ₽
                </span>
                <button
                  onClick={() => {
                    setEditBetValue(Math.round(effectiveBet).toString());
                    setIsEditingBet(true);
                  }}
                  className="text-gray-500 hover:text-white transition-colors p-1"
                  title="Изменить ставку или цвет при ошибке ввода"
                >
                  ✏️
                </button>
              </div>
            )}
          </div>

          {effectiveBet >= tableLimit && (
            <div className="mt-2 bg-red-600 text-white text-[10px] font-black px-3 py-1 rounded-full uppercase tracking-widest animate-pulse">
              ЛИМИТ СТОЛА ({tableLimit.toLocaleString('ru-RU')} ₽)
            </div>
          )}
        </motion.div>

        {/* CDT (Cumulative Debt Tracking) Monitor */}
        <div className={`p-3.5 rounded-2xl border-2 flex justify-between items-center transition-colors ${
          cdt === 0 ? 'bg-emerald-950/20 border-emerald-500/30' : 'bg-red-950/20 border-red-500/30'
        }`}>
          <div>
            <div className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Накопленный дефицит (CDT)</div>
            <div className={`text-xl font-mono font-black ${cdt === 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {Math.round(cdt).toLocaleString('ru-RU')} ₽
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Прогноз EV / Час</div>
            <div className={`text-xl font-mono font-black ${detailedStats.profitPerHour >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {detailedStats.profitPerHour >= 0 ? '+' : ''}{Math.round(detailedStats.profitPerHour).toLocaleString('ru-RU')} ₽
            </div>
          </div>
        </div>

        {/* INPUT ZONE (Optimized for Sub-10ms response) */}
        <div className="pt-2">
          <div className="text-center text-gray-500 text-[10px] font-bold tracking-widest uppercase mb-2.5 flex items-center justify-center gap-2">
            <span>Ввод результата</span>
            <span className="text-gray-600 font-mono">[Num 1: Красное | Num 2: Чёрное | Num 0: Зеро]</span>
          </div>
          <div className="grid grid-cols-3 gap-2.5">
            <button
              onClick={() => handleOutcome('RED')}
              className="bg-red-600 hover:bg-red-500 active:scale-95 transition-all h-22 rounded-2xl font-black text-xl tracking-wider shadow-[0_0_25px_rgba(220,38,38,0.35)] border border-red-500/50 flex flex-col items-center justify-center cursor-pointer"
            >
              <span>КРАСНОЕ</span>
              <span className="text-[10px] text-red-200 font-mono mt-0.5">[1] / [R]</span>
            </button>

            <button
              onClick={() => handleOutcome('ZERO')}
              className="bg-emerald-600 hover:bg-emerald-500 active:scale-95 transition-all h-22 rounded-2xl font-black text-xl tracking-wider shadow-[0_0_25px_rgba(16,185,129,0.35)] border border-emerald-500/50 flex flex-col items-center justify-center cursor-pointer"
            >
              <span>ЗЕРО</span>
              <span className="text-[10px] text-emerald-200 font-mono mt-0.5">[0] / [Z]</span>
            </button>

            <button
              onClick={() => handleOutcome('BLACK')}
              className="bg-gray-900 hover:bg-gray-800 active:scale-95 transition-all h-22 rounded-2xl font-black text-xl tracking-wider border border-gray-700 shadow-[0_0_25px_rgba(0,0,0,0.6)] flex flex-col items-center justify-center cursor-pointer"
            >
              <span>ЧЁРНОЕ</span>
              <span className="text-[10px] text-gray-400 font-mono mt-0.5">[2] / [B]</span>
            </button>
          </div>

          <div className="text-center text-gray-600 text-[10px] font-mono font-bold mt-2">
            ⏱ Цель: 8-10 сек между спинами | Текущий темп: {sessionLogs.length > 1 ? Math.round(sessionLogs.slice(-10).reduce((acc, l, i, arr) => i > 0 ? acc + (arr[i].time_since_last_spin || 0) : 0, 0) / Math.min(9, sessionLogs.length - 1) / 1000) : 0} сек
          </div>
        </div>

        {/* Undo Action */}
        <button
          onClick={handleUndo}
          disabled={history.length === 0}
          className="w-full py-3.5 rounded-2xl border border-gray-800 text-gray-400 hover:text-white hover:bg-gray-900 active:scale-95 transition-all flex items-center justify-center gap-2 disabled:opacity-40 disabled:pointer-events-none uppercase tracking-widest text-[11px] font-bold cursor-pointer"
        >
          <Undo2 size={15} /> Отменить Последний Ввод [Backspace / .]
        </button>

            {/* Risk Meter (Dynamic Durability to Table Ceiling) */}
            <div className="w-full bg-gray-900/60 rounded-2xl p-4 border border-gray-800">
              <div className="flex justify-between items-center text-[10px] font-bold text-gray-400 mb-2.5 tracking-widest uppercase font-mono">
                <span>Запас прочности: {currentStep} / {engineParams.stepsToLimit} шагов</span>
                <span className={currentStep >= engineParams.stepsToLimit ? 'text-amber-400 font-black animate-pulse' : 'text-emerald-400'}>
                  {Math.max(0, engineParams.stepsToLimit - currentStep)} шагов до потолка {(tableLimit / 1000000).toFixed(tableLimit % 1000000 === 0 ? 0 : 1)}М
                </span>
              </div>
              <div className="flex gap-1.5 h-3">
                {Array.from({ length: Math.max(8, engineParams.stepsToLimit) }, (_, idx) => idx + 1).map(i => {
                  let bgColor = 'bg-gray-800';
                  if (i <= currentStep) {
                    if (i <= Math.floor(engineParams.stepsToLimit * 0.4)) bgColor = 'bg-emerald-500';
                    else if (i <= Math.floor(engineParams.stepsToLimit * 0.7)) bgColor = 'bg-yellow-500';
                    else if (i < engineParams.stepsToLimit) bgColor = 'bg-red-500';
                    else bgColor = 'bg-amber-400 animate-pulse';
                  }
                  return (
                    <div
                      key={i}
                      className={`flex-1 rounded-sm ${bgColor} transition-colors duration-300`}
                      title={`Шаг ${i} из ${engineParams.stepsToLimit}`}
                    />
                  );
                })}
              </div>
              {currentStep >= engineParams.stepsToLimit && (
                <div className="mt-2.5 bg-amber-500/20 border border-amber-500/50 rounded-xl p-2 text-center text-amber-300 text-[10px] font-black uppercase tracking-wider">
                  ⚡ Терминальный шаг: ставка упирается в потолок ({Math.min(tableLimit, currentBankroll).toLocaleString('ru-RU')} ₽) для максимального съёма профита
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Deep Analytical Stream & Real-time Intelligence */}
          <div className="space-y-4">
            {/* Live Chart.js */}
            <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4">
              <div className="flex justify-between items-center mb-3">
                <div className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">График Баланса</div>
                <button
                  onClick={exportSessionLogs}
                  className="flex items-center gap-1 text-[10px] font-bold tracking-widest uppercase px-2.5 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors"
                >
                  <Download size={12} /> Экспорт JSON
                </button>
              </div>
              <div className="h-44 w-full">
                <Line data={chartData} options={chartOptions as any} />
              </div>
            </div>

            {/* Analytics Stream (Apex Matrix, Skew, Skew 15, Alpha/Omega) */}
            <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 space-y-3">
              <div className="flex justify-between items-center border-b border-gray-800 pb-2">
                <span className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Аналитика Потока</span>
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-black border ${
                  currentMode === 'DANGER' ? 'text-red-400 border-red-500/40' : 'text-emerald-400 border-emerald-500/40'
                }`}>
                  {currentMode === 'DANGER' ? 'DANGER' : `Уверенность: ${prediction.confidence}%`}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div>
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Глобально</div>
                  <div className="text-gray-300 font-bold">
                    К {Math.round(globalSkew.red)}% / Ч {Math.round(globalSkew.black)}%
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Локально (15)</div>
                  <div className="text-gray-300 font-bold">
                    К {Math.round(localSkew.red)}% / Ч {Math.round(localSkew.black)}%
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Альфа-Цвет</div>
                  <div className={`font-bold ${apexMatrix.alpha === 'RED' ? 'text-red-500' : apexMatrix.alpha === 'BLACK' ? 'text-gray-300' : 'text-gray-500'}`}>
                    {apexMatrix.alpha === 'RED' ? 'КРАСНОЕ' : apexMatrix.alpha === 'BLACK' ? 'ЧЁРНОЕ' : 'НЕТ'}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Макс. Серии (20)</div>
                  <div className="text-gray-300 font-bold">
                    К: {apexMatrix.maxStreakRed} / Ч: {apexMatrix.maxStreakBlack}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Распределение</div>
                  <div className="flex gap-1.5 font-bold">
                    <span className="text-red-500">{detailedStats.redCount} ({detailedStats.redPct}%)</span>
                    <span className="text-gray-400">{detailedStats.blackCount} ({detailedStats.blackPct}%)</span>
                    <span className="text-emerald-500">{detailedStats.zeroCount} ({detailedStats.zeroPct}%)</span>
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Текущая Серия</div>
                  <div className="text-white font-bold">
                    {detailedStats.currentStreakColor === 'RED' ? 'Красное' : detailedStats.currentStreakColor === 'BLACK' ? 'Чёрное' : detailedStats.currentStreakColor === 'ZERO' ? 'Зеро' : '-'} : {detailedStats.currentStreakLength}
                  </div>
                </div>
              </div>
            </div>

            {/* Deep Stats (Streak Avg, Zebra %, Zero Frequency) */}
            <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4">
              <div className="text-[10px] text-gray-400 uppercase tracking-widest font-bold mb-3">Глубокая Статистика</div>
              <div className="grid grid-cols-3 gap-2 text-center font-mono">
                <div className="bg-black/50 p-2 rounded-xl border border-gray-800">
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Ср. длина серии</div>
                  <div className="text-white font-bold text-sm">{detailedStats.avgStreakLength}</div>
                </div>
                <div className="bg-black/50 p-2 rounded-xl border border-gray-800">
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Коэф. Зебры</div>
                  <div className="text-emerald-400 font-bold text-sm">{detailedStats.zebraRatio}%</div>
                </div>
                <div className="bg-black/50 p-2 rounded-xl border border-gray-800">
                  <div className="text-[9px] text-gray-500 uppercase font-sans font-bold">Частота Зеро</div>
                  <div className="text-yellow-400 font-bold text-sm">{detailedStats.avgZeroFrequency}</div>
                </div>
              </div>
            </div>

            {/* History Rail */}
            <div className="space-y-1.5">
              <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">История спинов (последние 30)</div>
              <div className="flex gap-2 overflow-x-auto py-1 scrollbar-hide">
                {history.slice(-30).map(h => (
                  <HistoryIcon key={h.id} outcome={h.outcome} />
                ))}
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
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-gray-900 border border-gray-800 p-6 rounded-3xl max-w-sm w-full space-y-4"
            >
              <div className="flex justify-between items-center border-b border-gray-800 pb-3">
                <h3 className="font-bold text-sm uppercase tracking-wider text-white">Настройки Движка v12.5</h3>
                <button onClick={() => setShowProfileModal(false)} className="text-gray-500 hover:text-white cursor-pointer">✕</button>
              </div>

              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-2">Лимит / Потолок Стола</div>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setTableLimit(GAME_RULES.MAX_BET)}
                    className={`py-2 px-3 rounded-xl border text-xs font-mono font-bold transition-all cursor-pointer ${
                      tableLimit === GAME_RULES.MAX_BET
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
                        : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    1 000 000 ₽
                  </button>
                  <button
                    onClick={() => setTableLimit(GAME_RULES.VIP_MAX_BET)}
                    className={`py-2 px-3 rounded-xl border text-xs font-mono font-bold transition-all cursor-pointer ${
                      tableLimit === GAME_RULES.VIP_MAX_BET
                        ? 'bg-amber-500/20 border-amber-500 text-amber-300'
                        : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    2 000 000 ₽
                  </button>
                </div>
              </div>

              <div className="space-y-2.5">
                {(() => {
                  const zApex = BankrollManager.getCalibratedLadderConfig('APEX_IDEAL', 'ZEBRA', cycleCapital, tableLimit);
                  const tApex = BankrollManager.getCalibratedLadderConfig('APEX_IDEAL', 'TRANSITION', cycleCapital, tableLimit);
                  const dApex = BankrollManager.getCalibratedLadderConfig('APEX_IDEAL', 'DANGER', cycleCapital, tableLimit);
                  const zTurbo = BankrollManager.getCalibratedLadderConfig('TURBO_HARVEST', 'ZEBRA', cycleCapital, tableLimit);
                  const tTurbo = BankrollManager.getCalibratedLadderConfig('TURBO_HARVEST', 'TRANSITION', cycleCapital, tableLimit);
                  const dTurbo = BankrollManager.getCalibratedLadderConfig('TURBO_HARVEST', 'DANGER', cycleCapital, tableLimit);
                  const zShield = BankrollManager.getCalibratedLadderConfig('SHIELD_CONSERVATIVE', 'ZEBRA', cycleCapital, tableLimit);
                  const tShield = BankrollManager.getCalibratedLadderConfig('SHIELD_CONSERVATIVE', 'TRANSITION', cycleCapital, tableLimit);
                  const dShield = BankrollManager.getCalibratedLadderConfig('SHIELD_CONSERVATIVE', 'DANGER', cycleCapital, tableLimit);

                  return (
                    <>
                      <button
                        onClick={() => { setStrategyProfile('APEX_IDEAL'); setShowProfileModal(false); }}
                        className={`w-full p-3 rounded-2xl border text-left transition-all cursor-pointer ${
                          strategyProfile === 'APEX_IDEAL' ? 'bg-emerald-500/20 border-emerald-500 text-white' : 'bg-black/40 border-gray-800 text-gray-400'
                        }`}
                      >
                        <div className="font-bold text-emerald-400 text-xs flex items-center gap-1.5 mb-1">
                          <Sparkles size={14} /> APEX OPT (Золотой стандарт EV)
                        </div>
                        <div className="text-[11px] text-gray-300">
                          Без кулдауна + Zebra Lock. Зебра {zApex.baseBet.toLocaleString('ru-RU')} ₽ ({zApex.targetSteps} ш.), Переход {tApex.baseBet.toLocaleString('ru-RU')} ₽ ({tApex.targetSteps} ш.), Опасность {dApex.baseBet.toLocaleString('ru-RU')} ₽ ({dApex.targetSteps} ш.).
                        </div>
                      </button>

                      <button
                        onClick={() => { setStrategyProfile('TURBO_HARVEST'); setShowProfileModal(false); }}
                        className={`w-full p-3 rounded-2xl border text-left transition-all cursor-pointer ${
                          strategyProfile === 'TURBO_HARVEST' ? 'bg-amber-500/20 border-amber-500 text-white' : 'bg-black/40 border-gray-800 text-gray-400'
                        }`}
                      >
                        <div className="font-bold text-amber-400 text-xs flex items-center gap-1.5 mb-1">
                          <Zap size={14} /> TURBO HARVEST (Макс. темп 8 шагов)
                        </div>
                        <div className="text-[11px] text-gray-300">
                          Форсированный разгон прибыли (повышенный риск). Зебра {zTurbo.baseBet.toLocaleString('ru-RU')} ₽ ({zTurbo.targetSteps} ш.), Переход {tTurbo.baseBet.toLocaleString('ru-RU')} ₽ ({tTurbo.targetSteps} ш.), Опасность {dTurbo.baseBet.toLocaleString('ru-RU')} ₽ ({dTurbo.targetSteps} ш.).
                        </div>
                      </button>

                      <button
                        onClick={() => { setStrategyProfile('SHIELD_CONSERVATIVE'); setShowProfileModal(false); }}
                        className={`w-full p-3 rounded-2xl border text-left transition-all cursor-pointer ${
                          strategyProfile === 'SHIELD_CONSERVATIVE' ? 'bg-blue-500/20 border-blue-500 text-white' : 'bg-black/40 border-gray-800 text-gray-400'
                        }`}
                      >
                        <div className="font-bold text-blue-400 text-xs flex items-center gap-1.5 mb-1">
                          <Shield size={14} /> SHIELD ULTRA (Броня 10 шагов)
                        </div>
                        <div className="text-[11px] text-gray-300">
                          Максимальная выживаемость. Зебра {zShield.baseBet.toLocaleString('ru-RU')} ₽ ({zShield.targetSteps} ш.), Переход {tShield.baseBet.toLocaleString('ru-RU')} ₽ ({tShield.targetSteps} ш.), Опасность {dShield.baseBet.toLocaleString('ru-RU')} ₽ ({dShield.targetSteps} ш.).
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
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-gray-900 border border-emerald-500/30 p-8 rounded-3xl max-w-sm w-full text-center shadow-[0_0_50px_rgba(16,185,129,0.15)]"
            >
              <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/30">
                <CheckCircle2 className="text-emerald-400" size={32} />
              </div>
              <h2 className="text-2xl font-black tracking-tight mb-1 text-white">ЦЕЛЬ ДОСТИГНУТА</h2>
              <p className="text-gray-400 mb-6 text-xs">Зафиксирован профит +25%! Рекомендуется забрать выигрыш.</p>

              <div className="bg-black/60 rounded-2xl p-4 mb-6 border border-gray-800 font-mono">
                <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1 font-bold">ПРОФИТ СЕССИИ</div>
                <div className="text-3xl text-emerald-400 font-black">+{Math.round(profit).toLocaleString('ru-RU')} ₽</div>
              </div>

              <div className="space-y-2">
                <button
                  onClick={() => {
                    saveCurrentSession();
                    exportSessionLogs();
                    setShowSummary(false);
                    setInitialBankroll(0);
                    setHistory([]);
                    setCurrentStep(1);
                    setAttackStep(0);
                    setCdt(0);
                    setCurrentMode('ZEBRA');
                    setPreviousMode('ZEBRA');
                    setSpinsSinceDangerExit(999);
                    setSpinsInCurrentMode(0);
                    setSequenceStartMode('ZEBRA');
                    setSequenceTargetSteps(undefined);
                    localStorage.removeItem('matreshka_quantum_v12_state');
                  }}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-3.5 rounded-xl uppercase tracking-widest transition-colors text-xs cursor-pointer shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                >
                  Зафиксировать и Начать Заново
                </button>
                <button
                  onClick={() => setShowSummary(false)}
                  className="w-full py-3 text-gray-400 hover:text-white text-xs font-bold uppercase tracking-widest transition-colors"
                >
                  Продолжить Игру
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
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-gray-900 border border-red-500/40 p-8 rounded-3xl max-w-sm w-full text-center shadow-[0_0_50px_rgba(239,68,68,0.2)]"
            >
              <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-500/30">
                <AlertTriangle className="text-red-500" size={32} />
              </div>
              <h2 className="text-xl font-black tracking-tight mb-1 text-white">ЗАВЕРШИТЬ СЕССИЮ?</h2>
              <p className="text-gray-400 mb-6 text-xs">Текущие результаты будут сохранены в архив сессий.</p>

              <div className="flex gap-2">
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="flex-1 py-3 rounded-xl border border-gray-700 text-white font-bold uppercase tracking-widest hover:bg-gray-800 transition-colors text-xs cursor-pointer"
                >
                  Отмена
                </button>
                <button
                  onClick={() => {
                    saveCurrentSession();
                    exportSessionLogs();
                    setShowResetConfirm(false);
                    setInitialBankroll(0);
                    setHistory([]);
                    setCurrentStep(1);
                    setAttackStep(0);
                    setCdt(0);
                    setCurrentMode('ZEBRA');
                    setPreviousMode('ZEBRA');
                    setSpinsSinceDangerExit(999);
                    setSpinsInCurrentMode(0);
                    setSequenceStartMode('ZEBRA');
                    setSequenceTargetSteps(undefined);
                    localStorage.removeItem('matreshka_quantum_v12_state');
                  }}
                  className="flex-1 bg-red-600 hover:bg-red-500 text-white font-black py-3 rounded-xl uppercase tracking-widest transition-colors text-xs cursor-pointer shadow-[0_0_20px_rgba(239,68,68,0.3)]"
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
