'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { RotateCcw, Undo2, CheckCircle2, AlertTriangle, Info, Download } from 'lucide-react';
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

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

type Outcome = 'RED' | 'BLACK' | 'ZERO';

interface HistoryEntry {
  id: string;
  outcome: Outcome;
  betAmount: number;
  betColor: Outcome | 'WAIT';
  isWin: boolean;
  netProfit: number;
}

interface SavedSession {
  id: string;
  date: number;
  profit: number;
  durationMs: number;
  zeroCount: number;
  roi: number;
}

interface SessionLogEntry {
  timestamp: number;
  input_result: Outcome;
  recommended_action: Outcome | 'WAIT';
  current_bet: number;
  current_step: number;
  current_balance: number;
  server_state_detected: string;
  time_since_last_spin: number;
}

// Audio Engine
let audioCtx: AudioContext | null = null;
const initAudio = () => {
  if (!audioCtx && typeof window !== 'undefined') {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
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
  } catch (e) {
    console.error("Audio playback failed", e);
  }
};

const playClick = () => playTone(800, 'sine', 0.1, 0.05);
const playHum = () => playTone(60, 'sawtooth', 1.0, 0.1);
const playAlert = () => {
  playTone(880, 'square', 0.2, 0.05);
  setTimeout(() => playTone(1100, 'square', 0.4, 0.05), 200);
};

const calculateS = (hist: HistoryEntry[]) => {
  if (hist.length === 0) return 0;
  let streakLengths = new Array(hist.length).fill(0);
  let currentStreakColor: Outcome | null = hist[0].outcome;
  let currentStreakStart = 0;
  for (let i = 1; i <= hist.length; i++) {
    const color = i < hist.length ? hist[i].outcome : null;
    if (color !== currentStreakColor || color === 'ZERO') {
      const length = i - currentStreakStart;
      for (let j = currentStreakStart; j < i; j++) {
        streakLengths[j] = currentStreakColor === 'ZERO' ? 0 : length;
      }
      currentStreakColor = color;
      currentStreakStart = i;
    }
  }
  const last20 = streakLengths.slice(-20);
  const spinsInStreaks = last20.filter(len => len > 3).length;
  return spinsInStreaks / 20;
};

const getRecommendation = (hist: HistoryEntry[], attackStep: number, currentStep: number): Outcome | 'WAIT' => {
  if (hist.length === 0) return 'RED';

  if (attackStep > 0) {
      const lastOutcome = hist[hist.length - 1].outcome;
      return lastOutcome === 'ZERO' ? 'RED' : lastOutcome;
  }

  const S = calculateS(hist);

  if (hist.length >= 3) {
    const last3 = hist.slice(-3);
    const allRed = last3.every(h => h.outcome === 'RED');
    const allBlack = last3.every(h => h.outcome === 'BLACK');
    
    if (allRed || allBlack) {
      if (currentStep === 4) {
        if (S < 0.25) {
          return allRed ? 'BLACK' : 'RED';
        } else {
          return allRed ? 'RED' : 'BLACK';
        }
      }
      if (S < 0.25) {
         return allRed ? 'BLACK' : 'RED';
      } else {
         return allRed ? 'RED' : 'BLACK';
      }
    }
  }

  for (let i = hist.length - 1; i >= 0; i--) {
    if (hist[i].outcome === 'RED') return 'BLACK';
    if (hist[i].outcome === 'BLACK') return 'RED';
  }
  
  return 'RED';
};

export default function MatreshkaQuantum() {
  const [isClient, setIsClient] = useState(false);
  const [initialBankroll, setInitialBankroll] = useState<number>(0);
  const [minBet, setMinBet] = useState<number>(1000);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [showSummary, setShowSummary] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [setupVal, setSetupVal] = useState('');
  const [setupMinBet, setSetupMinBet] = useState('1000');
  const [autoScale, setAutoScale] = useState(false);
  const [zeroMessage, setZeroMessage] = useState(false);
  const [mode, setMode] = useState<'SAFE' | 'QUANT_YIELD'>('SAFE');
  const [attackStep, setAttackStep] = useState<number>(0);
  const [sessionStartTime, setSessionStartTime] = useState<number>(() => Date.now());
  const [now, setNow] = useState<number>(() => Date.now());
  const [savedSessions, setSavedSessions] = useState<SavedSession[]>([]);
  const [manualBet, setManualBet] = useState<number | null>(null);
  const [manualColor, setManualColor] = useState<Outcome | null>(null);
  const [isEditingBet, setIsEditingBet] = useState(false);
  const [editBetValue, setEditBetValue] = useState('');
  const [sessionLogs, setSessionLogs] = useState<SessionLogEntry[]>([]);

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsClient(true);
    const saved = localStorage.getItem('matreshka_state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setInitialBankroll(parsed.initialBankroll || 0);
        setMinBet(parsed.minBet || 1000);
        setHistory(parsed.history || []);
        setCurrentStep(parsed.currentStep || 1);
        setMode(parsed.mode || 'SAFE');
        setAttackStep(parsed.attackStep || 0);
        if (parsed.sessionStartTime) setSessionStartTime(parsed.sessionStartTime);
      } catch (e) {
        console.error("Failed to parse saved state", e);
      }
    }
    const sessions = localStorage.getItem('matreshka_sessions');
    if (sessions) {
      try {
        setSavedSessions(JSON.parse(sessions));
      } catch (e) {}
    }
  }, []);

  useEffect(() => {
    if (isClient && initialBankroll > 0) {
      localStorage.setItem('matreshka_state', JSON.stringify({
        initialBankroll, minBet, history, currentStep, mode, attackStep, sessionStartTime
      }));
    }
  }, [initialBankroll, minBet, history, currentStep, mode, attackStep, sessionStartTime, isClient]);

  const saveCurrentSession = () => {
    if (history.length === 0) return;
    const durationMs = Date.now() - sessionStartTime;
    const currentBankroll = initialBankroll + history.reduce((acc, curr) => acc + curr.netProfit, 0);
    const profit = currentBankroll - initialBankroll;
    const zeroCount = history.filter(h => h.outcome === 'ZERO').length;
    const roi = initialBankroll > 0 ? (profit / initialBankroll) * 100 : 0;
    const newSession: SavedSession = {
      id: Date.now().toString(),
      date: Date.now(),
      profit,
      durationMs,
      zeroCount,
      roi
    };
    const updatedSessions = [newSession, ...savedSessions].slice(0, 10);
    setSavedSessions(updatedSessions);
    localStorage.setItem('matreshka_sessions', JSON.stringify(updatedSessions));
  };

  useEffect(() => {
    if (autoScale) {
        const bankroll = Number(setupVal) || 0;
        let maxSafeBase = Math.floor(bankroll / 1020);
        
        let step8Multiplier = 1;
        for (let i = 1; i < 8; i++) {
            step8Multiplier *= 2.2;
        }
        const maxBaseCap = Math.floor(1000000 / step8Multiplier);
        
        if (maxSafeBase > maxBaseCap) {
            maxSafeBase = maxBaseCap;
        }
        if (maxSafeBase < 1000) {
            maxSafeBase = 1000;
        }
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSetupMinBet(maxSafeBase.toString());
    }
  }, [setupVal, autoScale]);

  if (!isClient) return null;

  if (initialBankroll === 0) {
    const parsedMinBet = Math.max(1000, Number(setupMinBet) || 1000);
    const optimalBalance = parsedMinBet * 1020;
    
    let maxSteps = 0;
    let currentLoss = 0;
    let stepBet = parsedMinBet;
    const parsedBankroll = Number(setupVal) || 0;
    
    while (currentLoss + stepBet <= parsedBankroll && maxSteps < 50) {
      maxSteps++;
      currentLoss += stepBet;
      stepBet = Math.round(stepBet * 2.2);
    }

    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4 font-sans text-white">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-md w-full bg-gray-900 p-8 rounded-2xl border border-gray-800 shadow-2xl"
        >
          <h1 className="text-2xl font-black text-white mb-2 text-center tracking-widest uppercase">Matreshka Quantum</h1>
          <p className="text-gray-500 text-center text-sm mb-8">Движок прогрессии 2.2x</p>
          <div className="space-y-6">
            <div>
              <label className="block text-gray-400 text-xs font-bold uppercase tracking-widest mb-2">Ваш Баланс (₽)</label>
              <input
                type="number"
                value={setupVal}
                onChange={e => setSetupVal(e.target.value)}
                className="w-full bg-black border border-gray-800 text-emerald-400 text-3xl p-4 rounded-xl focus:outline-none focus:border-emerald-500 transition-colors font-mono text-center"
                placeholder="1020000"
              />
            </div>
            <div>
              <label className="block text-gray-400 text-xs font-bold uppercase tracking-widest mb-2">Минимальная ставка стола (₽)</label>
              <input
                type="number"
                value={setupMinBet}
                onChange={e => setSetupMinBet(e.target.value)}
                onBlur={e => {
                  if (Number(e.target.value) < 1000) setSetupMinBet('1000');
                }}
                disabled={autoScale}
                className="w-full bg-black border border-gray-800 text-white text-xl p-4 rounded-xl focus:outline-none focus:border-gray-600 transition-colors font-mono text-center disabled:opacity-50"
                placeholder="1000"
              />
            </div>

            <div className="flex items-center gap-3">
              <button 
                onClick={() => setAutoScale(!autoScale)}
                className={`w-6 h-6 rounded flex items-center justify-center border ${autoScale ? 'bg-emerald-500 border-emerald-500' : 'bg-transparent border-gray-600'}`}
              >
                {autoScale && <CheckCircle2 size={14} className="text-black" />}
              </button>
              <span className="text-sm text-gray-300 font-bold uppercase tracking-widest">Авто-масштабирование ставки</span>
            </div>

            {parsedBankroll > 0 && (
              <div className="bg-gray-800/50 p-4 rounded-xl border border-gray-700">
                <div className="flex items-start gap-3">
                  <Info className="text-emerald-400 shrink-0 mt-0.5" size={18} />
                  <div>
                    <p className="text-sm text-gray-300 mb-1">
                      Для этой ставки рекомендуется баланс: <span className="font-bold text-white">{optimalBalance.toLocaleString('ru-RU')} ₽</span>
                    </p>
                    <p className="text-xs text-gray-400">
                      Ваш баланс выдержит <span className="font-bold text-emerald-400">{maxSteps}</span> шагов прогрессии.
                    </p>
                  </div>
                </div>
              </div>
            )}

            <button
              onClick={() => {
                const val = Number(setupVal);
                const minB = Math.max(1000, Number(setupMinBet));
                if (val > 0 && minB > 0) {
                  setInitialBankroll(val);
                  setMinBet(minB);
                  setHistory([]);
                  setCurrentStep(1);
                  setAttackStep(0);
                  setZeroMessage(false);
                  setSessionStartTime(Date.now());
                }
              }}
              disabled={!setupVal || Number(setupVal) <= 0 || !setupMinBet || Number(setupMinBet) <= 0}
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-4 rounded-xl uppercase tracking-widest disabled:opacity-50 transition-colors mt-4"
            >
              Запустить Движок
            </button>

            {savedSessions.length > 0 && (
              <div className="mt-8 border-t border-gray-800 pt-6">
                <h3 className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-4">Последние Сессии</h3>
                <div className="space-y-2 max-h-48 overflow-y-auto pr-2 scrollbar-hide">
                  {savedSessions.map((s, i) => (
                    <div key={s.id} className="bg-black/50 border border-gray-800 rounded-lg p-3 flex justify-between items-center">
                      <div>
                        <div className="text-xs text-gray-500 font-bold">Сессия №{savedSessions.length - i}</div>
                        <div className="text-[10px] text-gray-600">{Math.round(s.durationMs / 60000)} мин | Зеро: {s.zeroCount}</div>
                      </div>
                      <div className={`font-mono font-bold text-sm ${s.profit >= 0 ? 'text-emerald-400' : 'text-red-500'}`}>
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

  const currentBankroll = initialBankroll + history.reduce((acc, curr) => acc + curr.netProfit, 0);
  const profit = currentBankroll - initialBankroll;

  let nextBet = minBet;
  if (manualBet !== null) {
      nextBet = manualBet;
  } else if (attackStep > 0 && history.length > 0) {
      const lastBet = history[history.length - 1].betAmount || minBet;
      nextBet = Math.round(lastBet * 1.9);
  } else if (currentStep > 1 && history.length > 0) {
      const lastBet = history[history.length - 1].betAmount || minBet;
      nextBet = Math.round(lastBet * 2.2);
  } else {
      nextBet = minBet;
  }

  if (nextBet > currentBankroll && currentBankroll > 0) {
      nextBet = currentBankroll;
  }

  if (nextBet > 1000000) {
      nextBet = 1000000;
  }

  const isMaxLimit = nextBet >= 1000000;

  let remainingSteps = 0;
  let simulatedBankroll = currentBankroll;
  let simulatedBet = nextBet;
  let simAttackStep = attackStep;
  
  while (simulatedBankroll >= simulatedBet && simulatedBet <= 1000000 && remainingSteps < 20) {
    remainingSteps++;
    simulatedBankroll -= simulatedBet;
    if (remainingSteps === 1 && simAttackStep > 0) {
        simulatedBet = Math.round(simulatedBet * 1.9);
    } else {
        simulatedBet = Math.round(simulatedBet * 2.2);
    }
  }

  if (simulatedBankroll > 0 && simulatedBankroll < simulatedBet && simulatedBet <= 1000000 && remainingSteps < 20) {
      remainingSteps++;
  }

  const baseRecommendation = getRecommendation(history, attackStep, currentStep);
  const recommendation = manualColor !== null ? manualColor : baseRecommendation;
  const recommendationText = recommendation === 'RED' ? 'КРАСНОЕ' : recommendation === 'BLACK' ? 'ЧЕРНОЕ' : 'ЗЕРО';

  const recentBets = history.filter(h => h.betAmount > 0).slice(-20);
  
  const S = calculateS(history);
  let confidence = 'Низкая';
  if (S >= 0.35) confidence = 'Высокая';
  else if (S >= 0.15) confidence = 'Средняя';

  const durationMs = now - sessionStartTime;
  const profitPerHour = durationMs > 0 ? (profit / (durationMs / 3600000)) : 0;

  let maxDrawdown = 0;
  let peak = initialBankroll;
  let currentBankrollCalc = initialBankroll;
  for (const h of history) {
    currentBankrollCalc += h.netProfit;
    if (currentBankrollCalc > peak) {
      peak = currentBankrollCalc;
    }
    const drawdown = peak - currentBankrollCalc;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
    }
  }

  const redCount = history.filter(h => h.outcome === 'RED').length;
  const blackCount = history.filter(h => h.outcome === 'BLACK').length;
  const zeroCount = history.filter(h => h.outcome === 'ZERO').length;
  const totalSpins = history.length;
  const redPct = totalSpins > 0 ? Math.round((redCount / totalSpins) * 100) : 0;
  const blackPct = totalSpins > 0 ? Math.round((blackCount / totalSpins) * 100) : 0;
  const zeroPct = totalSpins > 0 ? Math.round((zeroCount / totalSpins) * 100) : 0;

  // Deep Stats
  let totalStreaks = 0;
  let totalStreakLength = 0;
  let colorChanges = 0;
  let zeroIntervals = [];
  let lastZeroIndex = -1;

  let currentStreakLen = 0;
  let currentStreakCol = null;

  for (let i = 0; i < history.length; i++) {
    const h = history[i];
    
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

  const avgStreakLength = totalStreaks > 0 ? (totalStreakLength / totalStreaks).toFixed(2) : '0.00';
  const zebraRatio = totalSpins > 1 ? Math.round((colorChanges / (totalSpins - 1)) * 100) : 0;
  const avgZeroFrequency = zeroIntervals.length > 0 ? (zeroIntervals.reduce((a, b) => a + b, 0) / zeroIntervals.length).toFixed(1) : 'N/A';

  let currentStreakColorHUD = null;
  let currentStreakLengthHUD = 0;
  if (history.length > 0) {
    currentStreakColorHUD = history[history.length - 1].outcome;
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].outcome === currentStreakColorHUD) {
        currentStreakLengthHUD++;
      } else {
        break;
      }
    }
  }

  let maxStreak = 0;
  let tempStreak = 0;
  let tempColor = null;
  for (const h of history) {
    if (h.outcome === tempColor) {
      tempStreak++;
    } else {
      tempColor = h.outcome;
      tempStreak = 1;
    }
    if (tempStreak > maxStreak) maxStreak = tempStreak;
  }
  const recentWins = recentBets.filter(h => h.isWin).length;
  const winrate = recentBets.length > 0 ? recentWins / recentBets.length : 0;

  let serverPhase = 'АНАЛИЗ ТРЕНДА';
  if (recentBets.length >= 5) {
    if (winrate > 0.45) serverPhase = 'СТАБИЛЬНО';
    else if (winrate < 0.30) serverPhase = 'СЛИВ';
    else serverPhase = 'НОРМА';
  }

  let currentStreak = 0;
  let dynamicExpectancy = -4.6;
  if (history.length > 0) {
    const lastWin = history[history.length - 1].isWin;
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].isWin === lastWin) {
        currentStreak++;
      } else {
        break;
      }
    }
    dynamicExpectancy = -4.6 + (lastWin ? currentStreak * 1.2 : -currentStreak * 1.5);
  }

  const handleOutcome = (outcome: Outcome) => {
    playClick();
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);

    let isWin = false;
    let netProfit = 0;
    let nextStep = currentStep;
    let nextAttackStep = attackStep;

    if (outcome === 'ZERO') {
      isWin = false;
      netProfit = recommendation !== 'WAIT' ? -nextBet : 0;
      nextStep = 1;
      nextAttackStep = 0;
      setZeroMessage(true);
      setTimeout(() => setZeroMessage(false), 4000);
    } else if (recommendation === outcome) {
      isWin = true;
      netProfit = nextBet * 0.98; // 2% tax on win
      
      if (mode === 'QUANT_YIELD') {
        const last3 = history.slice(-3);
        const isTrend = last3.length === 3 && last3.every(h => h.outcome === outcome);
        
        if (attackStep > 0) {
            if (attackStep < 3) {
                nextAttackStep = attackStep + 1;
                nextStep = 1;
            } else {
                nextAttackStep = 0;
                nextStep = 1;
            }
        } else if (isTrend) {
            nextAttackStep = 1;
            nextStep = 1;
        } else {
            nextAttackStep = 0;
            nextStep = 1;
        }
      } else {
        nextStep = 1;
        nextAttackStep = 0;
      }
    } else {
      isWin = false;
      netProfit = recommendation !== 'WAIT' ? -nextBet : 0;
      if (attackStep > 0) {
          nextStep = 2;
          nextAttackStep = 0;
      } else {
          nextStep = currentStep + 1;
      }
    }

    const newEntry: HistoryEntry = {
      id: `${history.length}-${outcome}`,
      outcome,
      betAmount: recommendation !== 'WAIT' ? nextBet : 0,
      betColor: recommendation,
      isWin,
      netProfit
    };

    const newHistory = [...history, newEntry];
    setHistory(newHistory);
    setCurrentStep(nextStep);
    setAttackStep(nextAttackStep);

    const nowMs = new Date().getTime();
    const timeSinceLast = sessionLogs.length > 0 ? nowMs - sessionLogs[sessionLogs.length - 1].timestamp : 0;
    
    const newLogEntry: SessionLogEntry = {
      timestamp: nowMs,
      input_result: outcome,
      recommended_action: recommendation,
      current_bet: recommendation !== 'WAIT' ? nextBet : 0,
      current_step: currentStep,
      current_balance: currentBankroll,
      server_state_detected: serverPhase,
      time_since_last_spin: timeSinceLast
    };
    setSessionLogs([...sessionLogs, newLogEntry]);

    if (nextStep === 5) playHum();
    if (nextStep >= 4) playAlert();

    const newBankroll = initialBankroll + newHistory.reduce((acc, curr) => acc + curr.netProfit, 0);
    if (newBankroll >= initialBankroll * 1.2 && !showSummary) {
      setShowSummary(true);
    }
  };

  const handleUndo = () => {
    if (history.length === 0) return;
    playClick();
    setManualBet(null);
    setManualColor(null);
    setIsEditingBet(false);
    const newHistory = [...history];
    newHistory.pop();
    setHistory(newHistory);

    const newSessionLogs = [...sessionLogs];
    newSessionLogs.pop();
    setSessionLogs(newSessionLogs);

    let step = 1;
    let aStep = 0;
    
    for (let i = 0; i < newHistory.length; i++) {
        const entry = newHistory[i];
        const rec = getRecommendation(newHistory.slice(0, i), aStep, step);
        
        if (entry.outcome === 'ZERO') {
            step = 1;
            aStep = 0;
        } else if (rec === entry.outcome) {
            if (mode === 'QUANT_YIELD') {
                const last3 = newHistory.slice(Math.max(0, i - 3), i);
                const isTrend = last3.length === 3 && last3.every(h => h.outcome === entry.outcome);
                
                if (aStep > 0) {
                    if (aStep < 3) {
                        aStep++;
                        step = 1;
                    } else {
                        aStep = 0;
                        step = 1;
                    }
                } else if (isTrend) {
                    aStep = 1;
                    step = 1;
                } else {
                    aStep = 0;
                    step = 1;
                }
            } else {
                step = 1;
                aStep = 0;
            }
        } else {
            if (aStep > 0) {
                step = 2;
                aStep = 0;
            } else {
                step++;
            }
        }
    }
    
    setCurrentStep(step);
    setAttackStep(aStep);
  };

  const handleTakeProfit = () => {
      setAttackStep(0);
      setCurrentStep(1);
      setManualBet(null);
      setManualColor(null);
      setIsEditingBet(false);
  };

  const exportSessionLogs = () => {
    const exportData = {
      metadata: {
        date: new Date(sessionStartTime).toISOString(),
        totalProfit: profit,
        maxDrawdown: maxDrawdown,
        durationMs: durationMs,
      },
      logs: sessionLogs
    };
    
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `matreshka_session_${new Date(sessionStartTime).toISOString().split('T')[0]}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

  const chartData = {
    labels: sessionLogs.map((_, index) => index + 1),
    datasets: [
      {
        label: 'Баланс',
        data: sessionLogs.map(log => log.current_balance),
        borderColor: 'rgb(16, 185, 129)',
        backgroundColor: 'rgba(16, 185, 129, 0.5)',
        pointRadius: sessionLogs.map(log => log.input_result === 'ZERO' ? 5 : 0),
        pointBackgroundColor: sessionLogs.map(log => log.input_result === 'ZERO' ? 'rgb(59, 130, 246)' : 'transparent'),
        pointBorderColor: sessionLogs.map(log => log.input_result === 'ZERO' ? 'rgb(59, 130, 246)' : 'transparent'),
        tension: 0.1,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += new Intl.NumberFormat('ru-RU').format(context.parsed.y) + ' ₽';
            }
            return label;
          }
        }
      }
    },
    scales: {
      x: {
        display: false,
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: 'rgba(255, 255, 255, 0.5)',
        }
      }
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-emerald-500/30 pb-12">
      {/* Header */}
      <header className="border-b border-gray-800 bg-[#050505]/80 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-md mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-[10px] font-bold tracking-widest text-gray-500 uppercase">Matreshka Quantum</h1>
              <span className="text-[10px] font-mono text-gray-600 bg-gray-900 px-1.5 py-0.5 rounded">
                {Math.floor(durationMs / 60000).toString().padStart(2, '0')}:
                {Math.floor((durationMs % 60000) / 1000).toString().padStart(2, '0')}
              </span>
            </div>
            <div className={`text-2xl font-mono font-black tracking-tighter ${profit >= 0 ? 'text-emerald-400' : 'text-red-500'}`}>
              {profit >= 0 ? '+' : ''}{Math.round(profit).toLocaleString('ru-RU')} ₽
            </div>
            <div className="text-[10px] text-gray-500 font-mono mt-0.5">
              Баланс: {Math.round(currentBankroll).toLocaleString('ru-RU')} ₽
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex bg-gray-900 rounded-lg p-1 border border-gray-800">
              <button 
                onClick={() => setMode('SAFE')}
                className={`px-2 py-1 text-[9px] sm:text-[10px] font-bold uppercase tracking-widest rounded-md transition-colors ${mode === 'SAFE' ? 'bg-gray-800 text-white' : 'text-gray-500 hover:text-gray-300'}`}
              >
                🛡️ SAFE
              </button>
              <button 
                onClick={() => setMode('QUANT_YIELD')}
                className={`px-2 py-1 text-[9px] sm:text-[10px] font-bold uppercase tracking-widest rounded-md transition-colors ${mode === 'QUANT_YIELD' ? 'bg-yellow-500/20 text-yellow-500' : 'text-gray-500 hover:text-gray-300'}`}
              >
                🔥 YIELD
              </button>
            </div>
            <button onClick={() => setShowResetConfirm(true)} className="text-gray-500 hover:text-white transition-colors p-2 bg-gray-900 rounded-lg border border-gray-800">
              <RotateCcw size={18} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-md mx-auto p-4 space-y-6">
        {/* Live Metrics */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4">
            <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1 font-bold">Состояние Сервера</div>
            <div className={`font-mono font-bold text-lg ${serverPhase === 'СТАБИЛЬНО' ? 'text-emerald-400' : serverPhase === 'СЛИВ' ? 'text-red-500' : 'text-yellow-500'}`}>
              {serverPhase}
            </div>
          </div>
          <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4">
            <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1 font-bold">Мат. Ожидание</div>
            <div className={`font-mono font-bold text-lg ${dynamicExpectancy >= 0 ? 'text-emerald-400' : 'text-red-500'}`}>
              {dynamicExpectancy > 0 ? '+' : ''}{dynamicExpectancy.toFixed(2)}%
            </div>
          </div>
        </div>

        {/* Main Display */}
        <motion.div
          key={`${currentStep}-${attackStep}`}
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={`relative overflow-hidden rounded-3xl p-8 border-2 flex flex-col items-center justify-center min-h-[240px] shadow-2xl
              ${attackStep > 0 ? 'bg-yellow-950/30 border-yellow-500/50 shadow-[0_0_40px_rgba(234,179,8,0.2)]' :
              recommendation === 'RED' ? 'bg-red-950/20 border-red-900/50 shadow-red-900/20' :
              recommendation === 'BLACK' ? 'bg-gray-900/50 border-gray-700 shadow-black/50' :
                'bg-gray-900/50 border-gray-800'}`}
        >
          <div className={`absolute top-4 left-5 font-black tracking-widest text-sm
            ${currentStep <= 3 ? 'text-emerald-400' : currentStep <= 6 ? 'text-yellow-500' : 'text-red-500'}`}>
            {attackStep > 0 ? `АТАКА: ШАГ ${attackStep}` : `ШАГ: ${currentStep}`}
          </div>

          {attackStep > 0 ? (
             <div className="text-yellow-500 text-xs font-bold tracking-widest uppercase mb-3 mt-4 animate-pulse">
               🔥 РЕЖИМ АТАКИ: РЕИНВЕСТ ПРОФИТА
             </div>
          ) : (
             <div className="text-gray-400 text-xs font-bold tracking-widest uppercase mb-3 mt-4">РЕКОМЕНДАЦИЯ</div>
          )}

          <div className={`text-5xl sm:text-6xl font-black tracking-tighter mb-4
              ${attackStep > 0 ? 'text-yellow-500' :
              recommendation === 'RED' ? 'text-red-500' :
              recommendation === 'BLACK' ? 'text-white' :
                'text-gray-500'}`}
          >
            {recommendationText}
          </div>

          <div className="text-3xl sm:text-4xl font-mono text-white font-bold tracking-tight flex items-center justify-center gap-3">
            {isEditingBet ? (
              <div className="flex flex-col items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400 text-2xl">СТАВКА:</span>
                  <input
                    type="number"
                    value={editBetValue}
                    onChange={(e) => setEditBetValue(e.target.value)}
                    className="bg-black/50 border border-gray-700 rounded px-3 py-1 text-3xl w-40 text-center text-white focus:outline-none focus:border-blue-500"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        const val = parseInt(editBetValue, 10);
                        if (!isNaN(val) && val >= 1000) {
                          setManualBet(val);
                        }
                        setIsEditingBet(false);
                      } else if (e.key === 'Escape') {
                        setIsEditingBet(false);
                      }
                    }}
                  />
                  <span className="text-gray-400 text-2xl">₽</span>
                </div>
                <div className="flex gap-3 items-center">
                  <button onClick={() => setManualColor('RED')} className={`w-12 h-12 rounded-full bg-red-600 shadow-[0_0_15px_rgba(220,38,38,0.5)] ${manualColor === 'RED' ? 'ring-4 ring-white' : ''}`}></button>
                  <button onClick={() => setManualColor('ZERO')} className={`w-12 h-12 rounded-full bg-emerald-600 shadow-[0_0_15px_rgba(16,185,129,0.5)] ${manualColor === 'ZERO' ? 'ring-4 ring-white' : ''}`}></button>
                  <button onClick={() => setManualColor('BLACK')} className={`w-12 h-12 rounded-full bg-gray-800 border border-gray-600 shadow-[0_0_15px_rgba(0,0,0,0.5)] ${manualColor === 'BLACK' ? 'ring-4 ring-white' : ''}`}></button>
                  <button onClick={() => {
                      const val = parseInt(editBetValue, 10);
                      if (!isNaN(val) && val >= 1000) {
                        setManualBet(val);
                      }
                      setIsEditingBet(false);
                  }} className="ml-4 bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded text-sm font-bold uppercase tracking-widest transition-colors">ОК</button>
                </div>
              </div>
            ) : (
              <>
                <span>СТАВКА: {Math.round(nextBet).toLocaleString('ru-RU')} ₽</span>
                <button
                  onClick={() => {
                    setEditBetValue(Math.round(nextBet).toString());
                    setIsEditingBet(true);
                  }}
                  className="text-gray-500 hover:text-white transition-colors"
                  title="Изменить ставку (мисклик)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                </button>
              </>
            )}
          </div>

          {attackStep > 0 && (
              <button 
                onClick={handleTakeProfit}
                className="mt-4 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-500 border border-yellow-500/50 px-4 py-2 rounded-full text-xs font-bold uppercase tracking-widest transition-colors"
              >
                Забрать прибыль и сбросить
              </button>
          )}

          {(currentStep === 4 || currentStep === 5) && attackStep === 0 && (
            <motion.button
              onClick={() => {
                setManualBet(1000);
                setManualColor('ZERO');
              }}
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
              className="mt-6 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 text-xs sm:text-sm font-black px-4 py-2 rounded-full border border-emerald-500/50 uppercase tracking-widest text-center cursor-pointer transition-colors"
            >
              Рекомендуемая страховка: 1,000 на Зеро
            </motion.button>
          )}

          {isMaxLimit && (
            <div className="absolute bottom-4 bg-red-600 text-white text-[10px] font-black px-4 py-1.5 rounded-full uppercase tracking-widest">
              Превышен Лимит Стола
            </div>
          )}
        </motion.div>

        <AnimatePresence>
          {zeroMessage && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="bg-emerald-900/40 border border-emerald-500/50 text-emerald-400 p-4 rounded-xl text-center text-sm font-bold tracking-widest uppercase"
            >
              Системный сброс. Начинаем с минимальной ставки
            </motion.div>
          )}
        </AnimatePresence>

        {/* Analytics HUD */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-5 space-y-4">
          <div className="flex justify-between items-center">
            <div className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">Аналитика потока</div>
            <div className={`text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded bg-black border ${
              confidence === 'Высокая' ? 'text-emerald-400 border-emerald-500/30' :
              confidence === 'Средняя' ? 'text-yellow-500 border-yellow-500/30' :
              'text-red-500 border-red-500/30'
            }`}>
              Уверенность: {confidence}
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Распределение</div>
              <div className="flex gap-2 text-xs font-mono font-bold">
                <span className="text-red-500">{redCount} ({redPct}%)</span>
                <span className="text-gray-400">{blackCount} ({blackPct}%)</span>
                <span className="text-emerald-500">{zeroCount} ({zeroPct}%)</span>
              </div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Прогноз / Час</div>
              <div className={`text-xs font-mono font-bold ${profitPerHour >= 0 ? 'text-emerald-400' : 'text-red-500'}`}>
                {profitPerHour >= 0 ? '+' : ''}{Math.round(profitPerHour).toLocaleString('ru-RU')} ₽
              </div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Текущая серия</div>
              <div className="text-xs font-mono font-bold text-white">
                {currentStreakColorHUD === 'RED' ? 'Красное' : currentStreakColorHUD === 'BLACK' ? 'Черное' : currentStreakColorHUD === 'ZERO' ? 'Зеро' : '-'} : {currentStreakLengthHUD}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Макс. серия</div>
              <div className="text-xs font-mono font-bold text-white">{maxStreak}</div>
            </div>
          </div>
        </div>

        {/* Deep Stats */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-5 space-y-4">
          <div className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">Глубокая статистика</div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Ср. длина серии</div>
              <div className="text-xs font-mono font-bold text-white">{avgStreakLength}</div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Коэф. Зебры</div>
              <div className="text-xs font-mono font-bold text-white">{zebraRatio}%</div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Частота Зеро</div>
              <div className="text-xs font-mono font-bold text-white">{avgZeroFrequency}</div>
            </div>
          </div>
        </div>

        {/* Live Chart */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-5">
          <div className="flex justify-between items-center mb-4">
            <div className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">График баланса</div>
            <button
              onClick={exportSessionLogs}
              className="flex items-center gap-1 text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded bg-gray-800 text-gray-300 hover:text-white transition-colors"
            >
              <Download size={12} /> Экспорт логов
            </button>
          </div>
          <div className="h-40 w-full">
            <Line data={chartData} options={chartOptions as any} />
          </div>
        </div>

        {/* Risk Meter */}
        <div className="w-full bg-gray-900/80 rounded-2xl p-5 border border-gray-800">
          <div className="flex justify-between items-center text-[10px] font-bold text-gray-500 mb-3 tracking-widest uppercase">
            <span>Безопасно</span>
            <span className="text-emerald-400">Запас прочности: {remainingSteps} промахов</span>
            <span className="text-red-500">Критически</span>
          </div>
          <div className="flex gap-1.5 h-3">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(i => {
              let bgColor = 'bg-gray-800';
              if (i <= currentStep) {
                if (i <= 3) bgColor = 'bg-emerald-500';
                else if (i <= 6) bgColor = 'bg-yellow-500';
                else bgColor = 'bg-red-500';
              }
              return (
                <div key={i} className={`flex-1 rounded-sm ${bgColor} transition-colors duration-300`} />
              )
            })}
          </div>
        </div>

        {/* History Rail */}
        <div className="flex gap-2 overflow-x-auto py-2 scrollbar-hide">
          {history.slice(-15).map(h => (
            <div key={h.id} className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white border-2
                ${h.outcome === 'RED' ? 'bg-red-600 border-red-500' :
                h.outcome === 'BLACK' ? 'bg-gray-900 border-gray-700' :
                  'bg-emerald-600 border-emerald-500'}`}
            >
              {h.outcome === 'RED' ? 'К' : h.outcome === 'BLACK' ? 'Ч' : 'З'}
            </div>
          ))}
        </div>

        {/* Input Zone */}
        <div className="pt-2">
          <div className="text-center text-gray-400 text-xs font-bold tracking-widest uppercase mb-3">Что выпало?</div>
          <div className="grid grid-cols-3 gap-3">
            <button onClick={() => handleOutcome('RED')} className="bg-red-600 hover:bg-red-500 active:scale-95 transition-all h-20 rounded-2xl font-black text-lg tracking-widest shadow-[0_0_20px_rgba(220,38,38,0.2)]">
              КРАСНОЕ
            </button>
            <button onClick={() => handleOutcome('ZERO')} className="bg-emerald-600 hover:bg-emerald-500 active:scale-95 transition-all h-20 rounded-2xl font-black text-lg tracking-widest shadow-[0_0_20px_rgba(16,185,129,0.2)]">
              ЗЕРО
            </button>
            <button onClick={() => handleOutcome('BLACK')} className="bg-gray-800 hover:bg-gray-700 active:scale-95 transition-all h-20 rounded-2xl font-black text-lg tracking-widest border border-gray-700 shadow-[0_0_20px_rgba(0,0,0,0.5)]">
              ЧЕРНОЕ
            </button>
          </div>
        </div>

        <button onClick={handleUndo} disabled={history.length === 0} className="w-full py-5 rounded-2xl border border-gray-800 text-gray-400 hover:text-white hover:bg-gray-900 active:scale-95 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:pointer-events-none uppercase tracking-widest text-xs font-bold mt-2">
          <Undo2 size={16} /> Отменить Последний Ввод
        </button>
      </main>

      {/* Session Summary Modal */}
      <AnimatePresence>
        {showSummary && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-gray-900 border border-emerald-500/30 p-8 rounded-3xl max-w-sm w-full text-center shadow-[0_0_50px_rgba(16,185,129,0.1)]"
            >
              <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle2 className="text-emerald-400" size={32} />
              </div>
              <h2 className="text-2xl font-black tracking-tighter mb-2 text-white">ЦЕЛЬ ДОСТИГНУТА</h2>
              <p className="text-gray-400 mb-6 text-sm">Вы достигли цели в 20% прибыли для этой сессии.</p>

              <div className="bg-black rounded-xl p-5 mb-6 border border-gray-800">
                <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-2 font-bold">Чистая Прибыль</div>
                <div className="text-3xl font-mono text-emerald-400 font-black">+{Math.round(profit).toLocaleString('ru-RU')} ₽</div>
              </div>

              <button
                onClick={() => {
                  saveCurrentSession();
                  setShowSummary(false);
                  setInitialBankroll(0);
                  setHistory([]);
                  setCurrentStep(1);
                  setAttackStep(0);
                  localStorage.removeItem('matreshka_state');
                }}
                className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-4 rounded-xl uppercase tracking-widest transition-colors text-sm"
              >
                Начать Новую Сессию
              </button>
              <button
                onClick={() => setShowSummary(false)}
                className="w-full mt-3 py-4 text-gray-500 hover:text-white text-xs font-bold uppercase tracking-widest transition-colors"
              >
                Продолжить Игру
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Hard Reset Modal */}
      <AnimatePresence>
        {showResetConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-gray-900 border border-red-500/30 p-8 rounded-3xl max-w-sm w-full text-center shadow-[0_0_50px_rgba(239,68,68,0.1)]"
            >
              <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                <AlertTriangle className="text-red-500" size={32} />
              </div>
              <h2 className="text-2xl font-black tracking-tighter mb-2 text-white">ПОЛНЫЙ СБРОС</h2>
              <p className="text-gray-400 mb-6 text-sm">Вы уверены, что хотите сбросить движок? Вся история сессии будет безвозвратно удалена.</p>

              <div className="flex gap-3">
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="flex-1 py-4 rounded-xl border border-gray-700 text-white font-bold uppercase tracking-widest hover:bg-gray-800 transition-colors text-sm"
                >
                  Отмена
                </button>
                <button
                  onClick={() => {
                    saveCurrentSession();
                    setShowResetConfirm(false);
                    setInitialBankroll(0);
                    setHistory([]);
                    setCurrentStep(1);
                    setAttackStep(0);
                    setShowSummary(false);
                    localStorage.removeItem('matreshka_state');
                  }}
                  className="flex-1 bg-red-600 hover:bg-red-500 text-white font-black py-4 rounded-xl uppercase tracking-widest transition-colors text-sm"
                >
                  Завершить Сессию
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
