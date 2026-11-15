"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.GAME_RULES = void 0;
exports.GAME_RULES = {
    TOTAL_SLOTS: 50,
    RED_SLOTS: 24,
    BLACK_SLOTS: 24,
    ZERO_SLOTS: 2,
    MIN_BET: 1000,
    MAX_BET: 1000000,
    TAX_RATE: 0.02, // 2% commission on net win (server floors net profit)
    WIN_NET_RATIO: 0.98, // Net profit multiplier (floor(bet * 98 / 100))
    EXPECTED_ZERO_INTERVAL: 25, // 50 / 2 = 25 spins
};
