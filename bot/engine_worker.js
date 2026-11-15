/**
 * Persistent Bridge to the Official Matreshka RP TypeScript Engine (v15.0 FINAL APEX).
 * Directly invokes lib/engine compiled bundle (bankroll-manager, prng-detector, risk-guard).
 * Zero deviation, 100.000% parity with web application on GitHub.
 */

const readline = require('readline');
const path = require('path');
const { BankrollManager, PrngDetector, RiskGuard, GAME_RULES } = require(path.join(__dirname, 'engine_dist'));

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

rl.on('line', (line) => {
    if (!line.trim()) return;
    try {
        const req = JSON.parse(line);
        const cmd = req.cmd;

        if (cmd === 'ping') {
            console.log(JSON.stringify({ status: 'ok', pong: true }));
        } else if (cmd === 'calc_bet') {
            const profile = req.profile || 'APEX_IDEAL';
            const bankroll = Math.floor(req.bankroll || 1000000);
            const cdt = Math.max(0, req.cdt || 0);
            const step = Math.max(1, req.step || 1);
            const currentMode = req.currentMode || 'ZEBRA';
            const sequenceStartMode = req.sequenceStartMode || 'ZEBRA';
            const sequenceTargetSteps = req.sequenceTargetSteps !== undefined ? req.sequenceTargetSteps : undefined;
            const zeroInSequence = req.zeroInSequence || 0;
            const history = req.history || [];

            // 1. Zero-Shock & Zebra Lock Detection
            const zeroCountLast10 = history.slice(-10).filter(h => h.outcome === 'ZERO').length;
            const cycleCapital = bankroll + cdt;
            const isZeroShock =
                profile !== 'SHIELD_CONSERVATIVE' &&
                BankrollManager.isZeroShockActive(zeroCountLast10, zeroInSequence);
            const isZebraLocked =
                cdt > 0 &&
                BankrollManager.shouldLockZebra(profile, cycleCapital, sequenceStartMode, isZeroShock);
            const effectiveMode = isZebraLocked ? 'ZEBRA' : currentMode;

            // 2. Engine Params
            const engineParams = BankrollManager.getEngineParams(
                profile,
                effectiveMode,
                bankroll,
                cdt,
                cdt > 0 ? sequenceTargetSteps : undefined,
                isZeroShock,
                step
            );

            // 3. Previous bet
            let prevBetAmount = undefined;
            if (step > 1 && history.length > 0) {
                prevBetAmount = history[history.length - 1].betAmount;
            }

            // 4. Calculate Bet
            const nextCalculatedBet = BankrollManager.calculateBet(
                cdt,
                step,
                effectiveMode,
                engineParams,
                bankroll,
                prevBetAmount
            );

            // 5. Prediction (v15.0 MPD + 24-spin rolling Half-Wheel Local Skew)
            const prediction = PrngDetector.getRecommendationAndConfidence(history);

            console.log(JSON.stringify({
                bet: nextCalculatedBet,
                recommendation: prediction.recommendation,
                confidence: prediction.confidence,
                state: prediction.state,
                effectiveMode,
                isZeroShock,
                isZebraLocked,
                engineParams
            }));
        } else if (cmd === 'process_outcome') {
            const profile = req.profile || 'APEX_IDEAL';
            const bankroll = Math.floor(req.bankroll || 1000000);
            const initialBankroll = Math.floor(req.initialBankroll || 1000000);
            const cdt = Math.max(0, req.cdt || 0);
            const step = Math.max(1, req.step || 1);
            const zeroInSequence = req.zeroInSequence || 0;
            const currentMode = req.currentMode || 'ZEBRA';
            const previousMode = req.previousMode || 'ZEBRA';
            const spinsSinceDangerExit = req.spinsSinceDangerExit !== undefined ? req.spinsSinceDangerExit : 999;
            const spinsInCurrentMode = req.spinsInCurrentMode !== undefined ? req.spinsInCurrentMode : 0;
            const sequenceStartMode = req.sequenceStartMode || 'ZEBRA';
            let sequenceTargetSteps = req.sequenceTargetSteps !== undefined ? req.sequenceTargetSteps : undefined;
            const history = req.history || [];
            const effectiveBet = req.effectiveBet;
            const recommendation = req.recommendation;
            const outcome = req.outcome; // 'RED', 'BLACK', 'ZERO'

            let isWin = false;
            let netProfit = 0;
            let nextStep = step;
            let nextCdt = cdt;
            let nextZeroInSeq = zeroInSequence;

            if (outcome === 'ZERO') {
                isWin = false;
                netProfit = -effectiveBet;
                nextCdt += effectiveBet;
                nextStep = step + 1;
                nextZeroInSeq++;
            } else if (recommendation === outcome) {
                isWin = true;
                netProfit = BankrollManager.calcNetWin(effectiveBet);
                nextCdt = Math.max(0, nextCdt - netProfit);
                if (nextCdt === 0) {
                    nextStep = 1;
                    nextZeroInSeq = 0;
                }
            } else {
                isWin = false;
                netProfit = -effectiveBet;
                nextCdt += effectiveBet;
                nextStep = step + 1;
            }

            // Terminal Sequence Loss Guard (100% Guaranteed Series Reset):
            // If the lost bet reached the table limit (1,000,000 RUB) or exhausted the target steps of the ladder,
            // the sequence is formally dead. Write off CDT to 0 and restart cleanly from Step 1.
            const isTerminalLoss = !isWin && BankrollManager.isTerminalSequenceLoss(
                step,
                sequenceTargetSteps,
                effectiveBet,
                GAME_RULES.MAX_BET
            );

            if (isTerminalLoss) {
                nextCdt = 0;
                nextStep = 1;
                nextZeroInSeq = 0;
            }

            const wasAtStart = cdt === 0 || step === 1;
            const newEntry = {
                id: `${history.length}-${outcome}-${Date.now()}`,
                outcome,
                betAmount: effectiveBet,
                betColor: recommendation,
                isWin,
                netProfit
            };
            const finalHistory = [...history, newEntry];

            // Mode updates
            let newMode;
            let newPrevMode;
            let newSpinsSinceDangerExit;
            let newSpinsInCurrentMode;

            if (BankrollManager.usesFastModeDetector(profile)) {
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

            // Sequence Target Steps update
            let nextSeqStart = sequenceStartMode;
            if (nextCdt === 0) {
                nextSeqStart = newMode;
                sequenceTargetSteps = undefined;
                nextZeroInSeq = 0;
            } else if (wasAtStart) {
                const startCfg = BankrollManager.getCalibratedLadderConfig(
                    profile,
                    currentMode,
                    bankroll
                );
                nextSeqStart = currentMode;
                sequenceTargetSteps = startCfg.targetSteps;
            } else {
                const nextZero10 = finalHistory.slice(-10).filter(h => h.outcome === 'ZERO').length;
                const nextZeroShock =
                    profile !== 'SHIELD_CONSERVATIVE' &&
                    BankrollManager.isZeroShockActive(nextZero10, nextZeroInSeq);
                if (nextZeroShock && nextStep >= 2) {
                    const nextCycleCap = bankroll + netProfit + nextCdt;
                    const expandedN = BankrollManager.getCalibratedLadderConfig(
                        profile,
                        newMode,
                        nextCycleCap
                    ).targetSteps;
                    sequenceTargetSteps = Math.min(10, Math.max(sequenceTargetSteps || expandedN, expandedN));
                }
            }

            // Detailed Stats
            const stats = RiskGuard.computeDetailedStats(
                finalHistory,
                initialBankroll,
                req.sessionStartTime || Date.now(),
                Date.now()
            );

            console.log(JSON.stringify({
                isWin,
                netProfit,
                newBankroll: bankroll + netProfit,
                nextCdt,
                nextStep,
                nextZeroInSeq,
                newMode,
                newPrevMode,
                newSpinsSinceDangerExit,
                newSpinsInCurrentMode,
                sequenceStartMode: nextSeqStart,
                sequenceTargetSteps,
                finalHistory,
                stats,
                isTerminalLoss: Boolean(isTerminalLoss)
            }));
        } else {
            console.log(JSON.stringify({ error: `Unknown command: ${cmd}` }));
        }
    } catch (err) {
        console.log(JSON.stringify({ error: err.message, stack: err.stack }));
    }
});
