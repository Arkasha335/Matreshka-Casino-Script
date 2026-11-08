'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { RotateCcw, Undo2, CheckCircle2, AlertTriangle, Info, Download, ShieldAlert, Zap, Sliders, Play, Pause } from 'lucide-react';
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
  AggressionProfile,
  EngineSettings,
  SpinRecord,
  PrngDetector,
  RiskGuard,
  BankrollManager
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

// Web Audio Synthesizer
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
    // Audio context may be restricted before user gesture
  }
};

const playClick = () => playTone(800, 'sine', 0.08, 0.04);
const playHapticClick = () => playTone(160, 'square', 0.04, 0.08);
const playSurgeWin = () => {
  playTone(587.33, 'triangle', 0.1, 0.06);
  setTimeout(() => playTone(880, 'triangle', 0.2, 0.08), 80);
};
const playZeroAlert = () => {
  playTone(440, 'sawtooth', 0.15, 0.08);
  setTimeout(() => playTone(330, 'sawtooth', 0.25, 0.08), 120);
};

const HistoryIcon = React.memo(function HistoryIcon({ outcome, isZeroFreeze }: { outcome: Outcome; isZeroFreeze?: boolean }) {
  return (
    <div
      className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white border-2 transition-transform hover:scale-110
        ${outcome === 'RED' ? 'bg-red-600 border-red-500 shadow-[0_0_10px_rgba(239,68,68,0.4)]' :
        outcome === 'BLACK' ? 'bg-gray-900 border-gray-700 shadow-[0_0_10px_rgba(0,0,0,0.6)]' :
        'bg-emerald-600 border-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.6)]'}
        ${isZeroFreeze ? 'ring-2 ring-amber-400' : ''}`}
      title={isZeroFreeze ? 'Спин в режиме ZERO-FREEZE' : undefined}
    >
      {outcome === 'RED' ? 'К' : outcome === 'BLACK' ? 'Ч' : 'З'}
    </div>
  );
});

export default function MatreshkaQuantum() {
  const [isClient, setIsClient] = useState(false);
  const [initialBankroll, setInitialBankroll] = useState<number>(0);
  const [records, setRecords] = useState<SpinRecord[]>([]);
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [surgeStep, setSurgeStep] = useState<number>(0);
  const [cdt, setCdt] = useState<number>(0);
  const [currentMode, setCurrentMode] = useState<ServerMode>('NEUTRAL');
  const [sessionStartTime, setSessionStartTime] = useState<number>(() => Date.now());
  const [now, setNow] = useState<number>(() => Date.now());

  // Settings
  const [aggressionProfile, setAggressionProfile] = useState<AggressionProfile>('HIGH_ROLLER_MAX');
  const [baseBetOverride, setBaseBetOverride] = useState<number | null>(null);
  const [stopLossPct, setStopLossPct] = useState<number>(0.15); // 15%
  const [takeProfitPct, setTakeProfitPct] = useState<number>(0.25); // 25%
  const [trailingStopPct, setTrailingStopPct] = useState<number>(0.04); // 4%
  const [zeroFreezeSpins, setZeroFreezeSpins] = useState<number>(3); // 3 spins freeze
  const [surgeCompoundEnabled, setSurgeCompoundEnabled] = useState<boolean>(true);

  // Manual inputs & UI state
  const [manualBet, setManualBet] = useState<number | null>(null);
  const [manualColor, setManualColor] = useState<Outcome | null>(null);
  const [isEditingBet, setIsEditingBet] = useState(false);
  const [editBetValue, setEditBetValue] = useState('');
  const [setupVal, setSetupVal] = useState('1000000');
  const [showSettings, setShowSettings] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  // Clock
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Restore State
  useEffect(() => {
    setIsClient(true);
    const saved = localStorage.getItem('matreshka_quantum_v11_state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.initialBankroll) setInitialBankroll(parsed.initialBankroll);
        if (parsed.records) setRecords(parsed.records);
        if (parsed.currentStep) setCurrentStep(parsed.currentStep);
        if (parsed.surgeStep) setSurgeStep(parsed.surgeStep);
        if (parsed.cdt !== undefined) setCdt(parsed.cdt);
        if (parsed.currentMode) setCurrentMode(parsed.currentMode);
        if (parsed.sessionStartTime) setSessionStartTime(parsed.sessionStartTime);
        if (parsed.aggressionProfile) setAggressionProfile(parsed.aggressionProfile);
        if (parsed.baseBetOverride !== undefined) setBaseBetOverride(parsed.baseBetOverride);
        if (parsed.stopLossPct) setStopLossPct(parsed.stopLossPct);
        if (parsed.takeProfitPct) setTakeProfitPct(parsed.takeProfitPct);
        if (parsed.zeroFreezeSpins !== undefined) setZeroFreezeSpins(parsed.zeroFreezeSpins);
        if (parsed.surgeCompoundEnabled !== undefined) setSurgeCompoundEnabled(parsed.surgeCompoundEnabled);
      } catch (e) {
        console.error('Failed to parse saved state', e);
      }
    }
  }, []);

  // Save State
  useEffect(() => {
    if (isClient && initialBankroll > 0) {
      localStorage.setItem('matreshka_quantum_v11_state', JSON.stringify({
        initialBankroll,
        records,
        currentStep,
        surgeStep,
        cdt,
        currentMode,
        sessionStartTime,
        aggressionProfile,
        baseBetOverride,
        stopLossPct,
        takeProfitPct,
        zeroFreezeSpins,
        surgeCompoundEnabled,
      }));
    }
  }, [
    isClient,
    initialBankroll,
    records,
    currentStep,
    surgeStep,
    cdt,
    currentMode,
    sessionStartTime,
    aggressionProfile,
    baseBetOverride,
    stopLossPct,
    takeProfitPct,
    zeroFreezeSpins,
    surgeCompoundEnabled
  ]);

  // Engine Settings Object
  const engineSettings: EngineSettings = useMemo(() => ({
    initialBankroll,
    aggressionProfile,
    baseBetOverride,
    stopLossPct,
    takeProfitPct,
    trailingStopPct,
    zeroFreezeSpins,
    maxStepCap: 4,
    surgeCompoundEnabled,
  }), [
    initialBankroll,
    aggressionProfile,
    baseBetOverride,
    stopLossPct,
    takeProfitPct,
    trailingStopPct,
    zeroFreezeSpins,
    surgeCompoundEnabled
  ]);

  // Derived Statistics
  const sessionStats = useMemo(() => {
    return RiskGuard.computeSessionStats(records, initialBankroll, sessionStartTime, now);
  }, [records, initialBankroll, sessionStartTime, now]);

  // Machine Prediction
  const prediction = useMemo(() => {
    return PrngDetector.predictNextOutcome(records);
  }, [records]);

  // Next Bet Calculation
  const nextBetCalc = useMemo(() => {
    return BankrollManager.calculateNextBet(
      sessionStats.currentBankroll,
      records,
      engineSettings,
      currentStep,
      surgeStep,
      cdt,
      currentMode
    );
  }, [sessionStats.currentBankroll, records, engineSettings, currentStep, surgeStep, cdt, currentMode]);

  const recommendedColor = manualColor !== null ? manualColor : prediction.recommendation;
  const effectiveBet = manualBet !== null ? manualBet : nextBetCalc.betAmount;

  // Outcome Handler
  const handleOutcome = useCallback((outcome: Outcome) => {
    playHapticClick();
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);

    if (outcome === 'ZERO') {
      playZeroAlert();
    }

    const { isWin, netProfit, nextStep, nextSurgeStep, nextCdt } = BankrollManager.processOutcome(
      outcome,
      recommendedColor,
      effectiveBet,
      currentStep,
      surgeStep,
      cdt,
      nextBetCalc.isFrozen
    );

    if (isWin && nextSurgeStep > 1) {
      playSurgeWin();
    }

    const nowMs = Date.now();
    const lastTimestamp = records.length > 0 ? records[records.length - 1].timestamp : sessionStartTime;
    const timeSinceLastSpin = nowMs - lastTimestamp;

    const newRecord: SpinRecord = {
      id: `${records.length + 1}-${outcome}-${nowMs}`,
      timestamp: nowMs,
      outcome,
      recommendedColor,
      betAmount: effectiveBet,
      isWin,
      netProfit,
      balance: sessionStats.currentBankroll + netProfit,
      mode: currentMode,
      step: currentStep,
      cdt: nextCdt,
      surgeStep,
      confidence: prediction.confidence,
      pattern: prediction.patternName,
      isZeroFreeze: nextBetCalc.isFrozen,
      timeSinceLastSpin,
    };

    const updatedRecords = [...records, newRecord];
    setRecords(updatedRecords);
    setCurrentStep(nextStep);
    setSurgeStep(nextSurgeStep);
    setCdt(nextCdt);

    // Update Mode based on CUSUM
    const cusum = PrngDetector.calcCusumState(updatedRecords, 25);
    if (cusum.state === 'BULLISH') {
      setCurrentMode('HARVEST');
    } else if (cusum.state === 'BEARISH') {
      setCurrentMode('DEFENSIVE');
    } else {
      setCurrentMode('NEUTRAL');
    }

    // Check Take-Profit Trigger
    if (sessionStats.totalProfit + netProfit >= initialBankroll * takeProfitPct && !showSummary) {
      setShowSummary(true);
    }
  }, [
    recommendedColor,
    effectiveBet,
    currentStep,
    surgeStep,
    cdt,
    nextBetCalc.isFrozen,
    records,
    sessionStartTime,
    sessionStats.currentBankroll,
    sessionStats.totalProfit,
    currentMode,
    prediction.confidence,
    prediction.patternName,
    initialBankroll,
    takeProfitPct,
    showSummary
  ]);

  // Undo Handler
  const handleUndo = useCallback(() => {
    if (records.length === 0) return;
    playClick();
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);

    const updatedRecords = records.slice(0, -1);
    setRecords(updatedRecords);

    // Replay state
    let step = 1;
    let sStep = 0;
    let currentCdt = 0;

    for (let i = 0; i < updatedRecords.length; i++) {
      const r = updatedRecords[i];
      if (r.isZeroFreeze || r.betAmount <= 0) continue;
      if (r.outcome === 'ZERO' || !r.isWin) {
        currentCdt += r.betAmount;
        step++;
        sStep = 0;
      } else {
        currentCdt = Math.max(0, currentCdt - r.netProfit);
        if (currentCdt < 50) {
          currentCdt = 0;
          step = 1;
          sStep++;
        } else {
          sStep = 0;
        }
      }
    }

    setCurrentStep(step);
    setSurgeStep(sStep);
    setCdt(currentCdt);
  }, [records]);

  // Keyboard Hotkeys
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
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

  // Export normalized logs
  const exportSessionLogs = useCallback(() => {
    const exportData = {
      metadata: {
        date: new Date(sessionStartTime).toISOString(),
        initialBankroll,
        currentBankroll: sessionStats.currentBankroll,
        totalProfit: sessionStats.totalProfit,
        maxDrawdown: sessionStats.maxDrawdown,
        durationMs: sessionStats.durationMs,
        aggressionProfile,
        winRate: sessionStats.winRate,
      },
      logs: records.map(r => ({
        timestamp: r.timestamp,
        input_result: r.outcome,
        recommended_action: r.recommendedColor,
        current_bet: r.betAmount,
        current_step: r.step,
        current_balance: r.balance,
        server_state_detected: r.pattern,
        time_since_last_spin: r.timeSinceLastSpin,
        current_mode: r.mode,
        is_win: r.isWin,
        net_profit: r.netProfit,
        is_zero_freeze: r.isZeroFreeze,
      }))
    };

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute('href', dataStr);
    downloadAnchorNode.setAttribute('download', `matreshka_quantum_v11_${new Date(sessionStartTime).toISOString().split('T')[0]}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  }, [sessionStartTime, initialBankroll, sessionStats, aggressionProfile, records]);

  // Chart Setup
  const chartData = useMemo(() => {
    return {
      labels: records.map((_, index) => index + 1),
      datasets: [
        {
          label: 'Баланс (₽)',
          data: records.map(r => r.balance),
          borderColor: sessionStats.totalProfit >= 0 ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)',
          backgroundColor: sessionStats.totalProfit >= 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          pointRadius: records.map(r => r.outcome === 'ZERO' ? 5 : 0),
          pointBackgroundColor: records.map(r => r.outcome === 'ZERO' ? 'rgb(234, 179, 8)' : 'transparent'),
          pointBorderColor: records.map(r => r.outcome === 'ZERO' ? '#fff' : 'transparent'),
          tension: 0.15,
          fill: true,
        },
      ],
    };
  }, [records, sessionStats.totalProfit]);

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
        grid: { color: 'rgba(255, 255, 255, 0.07)' },
        ticks: { color: 'rgba(255, 255, 255, 0.45)', font: { size: 10 } }
      }
    }
  }), []);

  if (!isClient) return null;

  // Onboarding screen
  if (initialBankroll === 0) {
    const parsedBankroll = Number(setupVal) || 0;
    const baseBetEst = BankrollManager.getRecommendedBaseBet(parsedBankroll, aggressionProfile);

    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center p-4 font-sans text-white">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-md w-full bg-gray-900/90 border border-emerald-500/30 p-8 rounded-3xl shadow-[0_0_60px_rgba(16,185,129,0.15)]"
        >
          <div className="flex items-center justify-center gap-2 mb-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
            <h1 className="text-xl font-black text-white tracking-widest uppercase">MATRESHKA QUANTUM</h1>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-400 font-bold px-2 py-0.5 rounded border border-emerald-500/30">v11.0</span>
          </div>
          <p className="text-gray-400 text-center text-xs mb-6">Квантовое ядро с защитой от слива и разгоном EV/час</p>

          <div className="space-y-5">
            <div>
              <label className="block text-gray-400 text-[10px] font-bold uppercase tracking-widest mb-1.5">Стартовый Баланс (₽)</label>
              <input
                type="number"
                value={setupVal}
                onChange={e => setSetupVal(e.target.value)}
                className="w-full bg-black/70 border border-gray-800 text-emerald-400 text-3xl p-4 rounded-2xl focus:outline-none focus:border-emerald-500 transition-colors font-mono text-center font-bold"
                placeholder="1000000"
              />
            </div>

            <div>
              <label className="block text-gray-400 text-[10px] font-bold uppercase tracking-widest mb-2">Профиль Агрессии (EV/час)</label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setAggressionProfile('HIGH_ROLLER_MAX')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 ${
                    aggressionProfile === 'HIGH_ROLLER_MAX'
                      ? 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-[0_0_20px_rgba(245,158,11,0.25)]'
                      : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  <Zap size={16} />
                  <span>MAX EV</span>
                  <span className="text-[9px] font-mono text-gray-400">High-Roller</span>
                </button>

                <button
                  type="button"
                  onClick={() => setAggressionProfile('BALANCED_QUANT')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 ${
                    aggressionProfile === 'BALANCED_QUANT'
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.25)]'
                      : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  <ShieldAlert size={16} />
                  <span>QUANT</span>
                  <span className="text-[9px] font-mono text-gray-400">Balanced</span>
                </button>

                <button
                  type="button"
                  onClick={() => setAggressionProfile('CONSERVATIVE_SHIELD')}
                  className={`p-3 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all flex flex-col items-center gap-1 ${
                    aggressionProfile === 'CONSERVATIVE_SHIELD'
                      ? 'bg-blue-500/20 border-blue-500 text-blue-300 shadow-[0_0_20px_rgba(59,130,246,0.25)]'
                      : 'bg-black/40 border-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  <CheckCircle2 size={16} />
                  <span>SHIELD</span>
                  <span className="text-[9px] font-mono text-gray-400">Low Risk</span>
                </button>
              </div>
            </div>

            {parsedBankroll > 0 && (
              <div className="bg-black/50 p-4 rounded-2xl border border-gray-800 text-xs text-gray-300 space-y-1.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-400">Базовая ставка (1-й шаг):</span>
                  <span className="font-bold text-white">{baseBetEst.toLocaleString('ru-RU')} ₽</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Zero-Freeze Фильтр:</span>
                  <span className="font-bold text-emerald-400">АКТИВЕН (3 спина)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Hard Stop-Loss:</span>
                  <span className="font-bold text-red-400">-{(stopLossPct * 100).toFixed(0)}% ({(parsedBankroll * stopLossPct).toLocaleString('ru-RU')} ₽)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Surge Волна (на победах):</span>
                  <span className="font-bold text-yellow-400">{aggressionProfile === 'HIGH_ROLLER_MAX' ? 'x5.5 Peak Compound' : 'x2.2 Compound'}</span>
                </div>
              </div>
            )}

            <button
              onClick={() => {
                const val = Number(setupVal);
                if (val > 0) {
                  setInitialBankroll(val);
                  setRecords([]);
                  setCurrentStep(1);
                  setSurgeStep(0);
                  setCdt(0);
                  setSessionStartTime(Date.now());
                }
              }}
              disabled={!setupVal || Number(setupVal) <= 0}
              className="w-full bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-black py-4 rounded-2xl uppercase tracking-widest disabled:opacity-50 transition-all shadow-[0_0_25px_rgba(16,185,129,0.3)] text-sm cursor-pointer"
            >
              Запустить Квантовое Ядро
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  const { totalProfit, currentBankroll, roi, profitPerHour, maxDrawdown, winRate, totalSpins } = sessionStats;
  const isPositive = totalProfit >= 0;

  return (
    <div className="min-h-screen bg-[#030712] text-white font-sans selection:bg-emerald-500/30 pb-16">
      {/* Top Bar */}
      <header className="border-b border-gray-800/80 bg-[#030712]/90 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-md mx-auto px-4 py-3 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-bold tracking-widest text-gray-400 uppercase">QUANTUM CORE v11.0</span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-500/30 px-1.5 py-0.2 rounded">
                {aggressionProfile === 'HIGH_ROLLER_MAX' ? 'MAX EV' : aggressionProfile === 'BALANCED_QUANT' ? 'QUANT' : 'SHIELD'}
              </span>
            </div>
            <div className={`text-2xl font-mono font-black tracking-tight ${isPositive ? 'text-emerald-400' : 'text-red-500'}`}>
              {isPositive ? '+' : ''}{Math.round(totalProfit).toLocaleString('ru-RU')} ₽
              <span className="text-xs text-gray-500 font-bold ml-1.5 font-sans">({roi.toFixed(1)}%)</span>
            </div>
            <div className="text-[11px] text-gray-400 font-mono">
              Баланс: <span className="font-bold text-white">{Math.round(currentBankroll).toLocaleString('ru-RU')} ₽</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="text-gray-400 hover:text-white transition-colors p-2.5 bg-gray-900 rounded-xl border border-gray-800"
              title="Настройки риск-профиля"
            >
              <Sliders size={18} />
            </button>
            <button
              onClick={() => setShowResetConfirm(true)}
              className="text-gray-400 hover:text-red-400 transition-colors p-2.5 bg-gray-900 rounded-xl border border-gray-800"
              title="Сброс сессии"
            >
              <RotateCcw size={18} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-md mx-auto p-4 space-y-4">
        {/* Settings Drawer */}
        <AnimatePresence>
          {showSettings && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="bg-gray-900/90 border border-gray-800 rounded-2xl p-4 overflow-hidden text-xs space-y-3"
            >
              <div className="flex justify-between items-center border-b border-gray-800 pb-2">
                <span className="font-bold uppercase tracking-wider text-gray-300">Настройки Риск-Менеджмента</span>
                <button onClick={() => setShowSettings(false)} className="text-gray-500 hover:text-white">✕</button>
              </div>

              <div>
                <span className="text-gray-400 block mb-1">Профиль агрессии:</span>
                <div className="grid grid-cols-3 gap-1.5">
                  {(['HIGH_ROLLER_MAX', 'BALANCED_QUANT', 'CONSERVATIVE_SHIELD'] as AggressionProfile[]).map(p => (
                    <button
                      key={p}
                      onClick={() => setAggressionProfile(p)}
                      className={`py-1.5 px-2 rounded-lg text-[10px] font-bold uppercase ${
                        aggressionProfile === p ? 'bg-emerald-600 text-white' : 'bg-black/50 text-gray-400 border border-gray-800'
                      }`}
                    >
                      {p === 'HIGH_ROLLER_MAX' ? 'Max EV' : p === 'BALANCED_QUANT' ? 'Quant' : 'Shield'}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-gray-400 block mb-1">Stop-Loss (%):</span>
                  <input
                    type="number"
                    value={Math.round(stopLossPct * 100)}
                    onChange={e => setStopLossPct(Math.max(5, Math.min(50, Number(e.target.value))) / 100)}
                    className="w-full bg-black/60 border border-gray-800 rounded-lg p-2 font-mono text-center text-red-400 font-bold"
                  />
                </div>
                <div>
                  <span className="text-gray-400 block mb-1">Take-Profit (%):</span>
                  <input
                    type="number"
                    value={Math.round(takeProfitPct * 100)}
                    onChange={e => setTakeProfitPct(Math.max(10, Math.min(100, Number(e.target.value))) / 100)}
                    className="w-full bg-black/60 border border-gray-800 rounded-lg p-2 font-mono text-center text-emerald-400 font-bold"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-gray-400">Zero-Freeze Кулдаун:</span>
                <div className="flex gap-1">
                  {[0, 1, 2, 3, 4].map(s => (
                    <button
                      key={s}
                      onClick={() => setZeroFreezeSpins(s)}
                      className={`w-7 h-7 rounded-lg text-xs font-bold font-mono ${
                        zeroFreezeSpins === s ? 'bg-amber-500 text-black' : 'bg-black border border-gray-800 text-gray-400'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-gray-400">Surge Волна (Compound):</span>
                <button
                  onClick={() => setSurgeCompoundEnabled(!surgeCompoundEnabled)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${
                    surgeCompoundEnabled ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-gray-800 text-gray-500'
                  }`}
                >
                  {surgeCompoundEnabled ? 'ВКЛ' : 'ВЫКЛ'}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Zero Freeze Warning Banner */}
        {nextBetCalc.isFrozen && nextBetCalc.riskStatus === 'ZERO_FREEZE' && (
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-amber-500/15 border-2 border-amber-500 rounded-2xl p-4 text-center shadow-[0_0_30px_rgba(245,158,11,0.25)] animate-pulse"
          >
            <div className="flex items-center justify-center gap-2 text-amber-400 font-black text-sm uppercase tracking-wider mb-1">
              <ShieldAlert size={18} />
              <span>РЕЖИМ ZERO-FREEZE АКТИВЕН</span>
            </div>
            <p className="text-amber-200 text-xs">
              Выпал сектор ЗЕРО. Чтобы не попасть в дуплет (27.5% аномалия), пропустите <span className="font-bold underline">{nextBetCalc.freezeRemaining} спин(а)</span> без реальной ставки!
            </p>
          </motion.div>
        )}

        {/* Stop Loss / Take Profit Locked Banner */}
        {nextBetCalc.riskStatus === 'STOP_LOSS_TRIPPED' && (
          <div className="bg-red-500/20 border-2 border-red-500 rounded-2xl p-4 text-center shadow-[0_0_30px_rgba(239,68,68,0.3)]">
            <div className="text-red-400 font-black text-sm uppercase tracking-wider mb-1">⛔ СТОП-ЛОСС СРАБОТАЛ</div>
            <p className="text-gray-300 text-xs">{nextBetCalc.riskMessage}</p>
          </div>
        )}

        {/* Main Quantum Display Card */}
        <motion.div
          key={`${currentStep}-${surgeStep}-${recommendedColor}`}
          initial={{ scale: 0.98, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={`relative overflow-hidden rounded-3xl p-6 border-2 flex flex-col items-center justify-center min-h-[250px] shadow-2xl transition-all
            ${nextBetCalc.isFrozen ? 'bg-gray-950 border-amber-500/80 shadow-[0_0_40px_rgba(245,158,11,0.2)]' :
            currentMode === 'HARVEST' ? 'bg-gray-950 border-emerald-500 shadow-[0_0_45px_rgba(16,185,129,0.25)]' :
            currentMode === 'DEFENSIVE' ? 'bg-gray-950 border-yellow-500 shadow-[0_0_40px_rgba(234,179,8,0.2)]' :
            'bg-gray-950 border-gray-800 shadow-[0_0_30px_rgba(0,0,0,0.8)]'}`}
        >
          {/* Top Indicators */}
          <div className="w-full flex justify-between items-center mb-2">
            <div className="flex items-center gap-1.5">
              <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full border ${
                currentStep === 1 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
                currentStep <= 3 ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30' :
                'bg-red-500/10 text-red-400 border-red-500/30'
              }`}>
                {nextBetCalc.riskStatus === 'AMORTIZING' ? 'АМОРТИЗАЦИЯ' :
                 surgeStep > 0 ? `SURGE: ШАГ ${surgeStep}` : `ШАГ: ${currentStep}/4`}
              </span>
              {surgeStep > 0 && (
                <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Zap size={10} /> ВОЛНА
                </span>
              )}
            </div>

            <div className="text-right">
              <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border ${
                currentMode === 'HARVEST' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' :
                currentMode === 'DEFENSIVE' ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30' :
                'bg-gray-800 text-gray-400 border-gray-700'
              }`}>
                {currentMode === 'HARVEST' ? '🟢 HARVEST (EV+)' : currentMode === 'DEFENSIVE' ? '🟡 DEFENSIVE' : '⚪ NEUTRAL'}
              </span>
            </div>
          </div>

          {/* Subtitle / Pattern Info */}
          <div className="text-[11px] font-bold text-gray-400 tracking-wider uppercase mb-1 flex items-center gap-1">
            <span>{prediction.patternName}</span>
            <span className="text-gray-600">•</span>
            <span className="text-emerald-400 font-mono">{prediction.confidence}% уверенность</span>
          </div>

          {/* Recommendation Color */}
          <div className={`text-6xl sm:text-7xl font-black tracking-tighter my-2 drop-shadow-lg ${
            recommendedColor === 'RED' ? 'text-red-500' :
            recommendedColor === 'BLACK' ? 'text-white' : 'text-emerald-400'
          }`}>
            {recommendedColor === 'RED' ? 'КРАСНОЕ' : recommendedColor === 'BLACK' ? 'ЧЁРНОЕ' : 'ЗЕРО'}
          </div>

          {/* Bet Display or Edit Mode */}
          <div className="mt-1 flex items-center justify-center gap-3">
            {isEditingBet ? (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={editBetValue}
                  onChange={e => setEditBetValue(e.target.value)}
                  className="bg-black border border-emerald-500 text-2xl font-mono text-center w-36 py-1 rounded-xl text-white focus:outline-none"
                  autoFocus
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      const val = Number(editBetValue);
                      if (val > 0) setManualBet(val);
                      setIsEditingBet(false);
                    } else if (e.key === 'Escape') {
                      setIsEditingBet(false);
                    }
                  }}
                />
                <button
                  onClick={() => {
                    const val = Number(editBetValue);
                    if (val > 0) setManualBet(val);
                    setIsEditingBet(false);
                  }}
                  className="bg-emerald-600 px-3 py-1 rounded-lg text-xs font-bold"
                >
                  OK
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-3xl sm:text-4xl font-mono font-black text-white">
                  {nextBetCalc.isFrozen ? (
                    <span className="text-amber-400 font-sans text-xl">ПРОПУСК (0 ₽)</span>
                  ) : (
                    `${Math.round(effectiveBet).toLocaleString('ru-RU')} ₽`
                  )}
                </span>
                {!nextBetCalc.isFrozen && (
                  <button
                    onClick={() => {
                      setEditBetValue(Math.round(effectiveBet).toString());
                      setIsEditingBet(true);
                    }}
                    className="text-gray-500 hover:text-white transition-colors p-1"
                    title="Ручной ввод размера ставки"
                  >
                    ✏️
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Risk Message Note */}
          <div className="mt-2 text-[10px] text-gray-400 text-center font-mono">
            {nextBetCalc.riskMessage}
          </div>
        </motion.div>

        {/* CDT / Deficit Gauge */}
        <div className={`p-3.5 rounded-2xl border flex justify-between items-center transition-colors ${
          cdt === 0 ? 'bg-emerald-950/20 border-emerald-500/30' : 'bg-red-950/20 border-red-500/30'
        }`}>
          <div>
            <div className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Накопленный дефицит (CDT)</div>
            <div className={`text-lg font-mono font-black ${cdt === 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {Math.round(cdt).toLocaleString('ru-RU')} ₽
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">EV / Час (Текущий темп)</div>
            <div className={`text-lg font-mono font-black ${profitPerHour >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {profitPerHour >= 0 ? '+' : ''}{Math.round(profitPerHour).toLocaleString('ru-RU')} ₽/ч
            </div>
          </div>
        </div>

        {/* INPUT ZONE (Optimized for Sub-10ms response) */}
        <div className="pt-2">
          <div className="text-center text-gray-500 text-[10px] font-bold tracking-widest uppercase mb-2.5 flex items-center justify-center gap-2">
            <span>Ввод результата</span>
            <span className="text-gray-600 font-mono">(Num 1: К | Num 2: Ч | Num 0: Зеро)</span>
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
        </div>

        {/* Undo Action */}
        <button
          onClick={handleUndo}
          disabled={records.length === 0}
          className="w-full py-3 rounded-xl border border-gray-800 text-gray-400 hover:text-white hover:bg-gray-900 active:scale-95 transition-all flex items-center justify-center gap-2 disabled:opacity-40 disabled:pointer-events-none uppercase tracking-widest text-[11px] font-bold cursor-pointer"
        >
          <Undo2 size={14} /> Отменить Последний Спин [Backspace / .]
        </button>

        {/* Live Metrics Grid */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 text-xs font-mono space-y-3">
          <div className="flex justify-between items-center text-gray-400 border-b border-gray-800 pb-2">
            <span className="font-sans font-bold uppercase text-[10px] tracking-wider text-gray-400">Метрики Потока</span>
            <span className="text-white font-bold">{totalSpins} спинов ({winRate.toFixed(1)}% Win)</span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-black/40 p-2 rounded-xl border border-gray-800/80">
              <div className="text-[9px] text-gray-500 uppercase font-sans">Чередование</div>
              <div className="font-bold text-white text-sm">{(prediction.alternationRate * 100).toFixed(0)}%</div>
            </div>
            <div className="bg-black/40 p-2 rounded-xl border border-gray-800/80">
              <div className="text-[9px] text-gray-500 uppercase font-sans">CUSUM Фаза</div>
              <div className={`font-bold text-sm ${
                prediction.cusumState === 'BULLISH' ? 'text-emerald-400' :
                prediction.cusumState === 'BEARISH' ? 'text-red-400' : 'text-gray-300'
              }`}>
                {prediction.cusumState}
              </div>
            </div>
            <div className="bg-black/40 p-2 rounded-xl border border-gray-800/80">
              <div className="text-[9px] text-gray-500 uppercase font-sans">Max Drawdown</div>
              <div className="font-bold text-red-400 text-sm">-{maxDrawdown.toLocaleString('ru-RU')} ₽</div>
            </div>
          </div>
        </div>

        {/* Live Equity Chart */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4">
          <div className="flex justify-between items-center mb-3">
            <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">Кривая Капитала</span>
            <button
              onClick={exportSessionLogs}
              className="flex items-center gap-1 text-[10px] font-bold tracking-widest uppercase px-2.5 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors"
            >
              <Download size={12} /> Экспорт JSON
            </button>
          </div>
          <div className="h-36 w-full">
            <Line data={chartData} options={chartOptions as any} />
          </div>
        </div>

        {/* Recent History Badges */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">История последних спинов (30)</div>
          <div className="flex gap-2 overflow-x-auto py-1.5 scrollbar-hide">
            {records.slice(-30).map(r => (
              <HistoryIcon key={r.id} outcome={r.outcome} isZeroFreeze={r.isZeroFreeze} />
            ))}
          </div>
        </div>
      </main>

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
              className="bg-gray-900 border border-emerald-500/40 p-8 rounded-3xl max-w-sm w-full text-center shadow-[0_0_60px_rgba(16,185,129,0.2)]"
            >
              <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/30">
                <CheckCircle2 className="text-emerald-400" size={32} />
              </div>
              <h2 className="text-2xl font-black tracking-tight mb-1 text-white">ЦЕЛЬ ДОСТИГНУТА</h2>
              <p className="text-gray-400 mb-6 text-xs">Зафиксирован профит +{(takeProfitPct * 100).toFixed(0)}%! Защитите прибыль от дисперсии.</p>

              <div className="bg-black/60 rounded-2xl p-4 mb-6 border border-gray-800 font-mono">
                <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1 font-bold">ЧИСТЫЙ ПРОФИТ</div>
                <div className="text-3xl text-emerald-400 font-black">+{Math.round(totalProfit).toLocaleString('ru-RU')} ₽</div>
              </div>

              <div className="space-y-2">
                <button
                  onClick={() => {
                    exportSessionLogs();
                    setShowSummary(false);
                    setInitialBankroll(0);
                    setRecords([]);
                    setCurrentStep(1);
                    setSurgeStep(0);
                    setCdt(0);
                    localStorage.removeItem('matreshka_quantum_v11_state');
                  }}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-3.5 rounded-xl uppercase tracking-widest transition-colors text-xs cursor-pointer shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                >
                  Зафиксировать и Выйти
                </button>
                <button
                  onClick={() => setShowSummary(false)}
                  className="w-full py-3 text-gray-400 hover:text-white text-xs font-bold uppercase tracking-widest transition-colors"
                >
                  Продолжить сессию
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
              className="bg-gray-900 border border-red-500/40 p-8 rounded-3xl max-w-sm w-full text-center shadow-[0_0_60px_rgba(239,68,68,0.2)]"
            >
              <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-500/30">
                <AlertTriangle className="text-red-500" size={32} />
              </div>
              <h2 className="text-xl font-black tracking-tight mb-1 text-white">ЗАВЕРШИТЬ СЕССИЮ?</h2>
              <p className="text-gray-400 mb-6 text-xs">Текущие логи будут сохранены, а состояние движка сбросится.</p>

              <div className="flex gap-2">
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="flex-1 py-3 rounded-xl border border-gray-700 text-white font-bold uppercase tracking-widest hover:bg-gray-800 transition-colors text-xs cursor-pointer"
                >
                  Отмена
                </button>
                <button
                  onClick={() => {
                    exportSessionLogs();
                    setShowResetConfirm(false);
                    setInitialBankroll(0);
                    setRecords([]);
                    setCurrentStep(1);
                    setSurgeStep(0);
                    setCdt(0);
                    localStorage.removeItem('matreshka_quantum_v11_state');
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
