# Synclavix – Architecture Overview

## 1. High‑Level Flow


## 2. Core Modules

| Module | File | Description |
|--------|------|-------------|
| **DXY Filter** | `modules/dxy_filter.py` | Fetches DXY via `yfinance`. Returns BULLISH/BEARISH/NEUTRAL; penalty 0.15 if BEARISH. |
| **Momentum Filter** | `modules/momentum_filter.py` | Strategy E: RSI 45‑65 + MACD cross + EMA50>EMA200 + cumulative delta lookback 3. Pre‑filter before LLM. |
| **SMC Context** | `modules/smc_context.py` | Detects Order Blocks, Fair Value Gaps, Liquidity Sweep. Adds context to LLM prompt. |
| **Screener** | `modules/screener.py` | Multi‑asset scanning (crypto + stocks/ETFs) with manipulation firewall, dynamic Kelly caps. Outputs `ACTIVE_ASSETS`. |
| **Narrative Scanner** | `modules/narrative_scanner.py` | Keyword scoring + LLM voting → active narratives. Falls back to keyword scores if LLM fails. |
| **LLM Clients** | `modules/llm_clients.py` | Wrapper for OpenRouter (6 models: Qwen, DeepSeek, Claude, GPT, Grok, Gemini). |
| **Dynamic Weights** | `modules/dynamic_weights.py` | ELO + win‑rate + profit → per‑LLM weight. |
| **Portfolio Manager** | `modules/portfolio_manager.py` | Tracks positions, applies trailing stop, partial TP, risk limits. |
| **Performance Boost** | `modules/performance_boost.py` | Fear & Greed, VIX regime, Kelly multiplier, circuit breaker. |
| **Cot Weekly** | `modules/cot_weekly.py` | Weekly self‑evaluation and Telegram report. |
| **Self‑Improvement** | `modules/self_improvement.py` | Weekly evaluation + backtest‑based parameter suggestions. |
| **Decision Context** | `modules/decision_context.py` | Logs full decision context for each trade. |

## 3. State Management & Pipeline

The pipeline is orchestrated by a state machine (`main.py`). States:
- **COLLECT**: Fetch market data, news, fear & greed, VIX.
- **ANALYZE**: Run filters, narrative, screener, and LLM council.
- **RISK_CHECK**: Apply Kelly, circuit breaker, correlation filter.
- **EXECUTE**: Send orders via exchange API.
- **RECONCILE**: Update positions, logs, and checkpoint.

All state transitions are checkpointed to `data/checkpoints/` and `data/session_state.json` for crash recovery.

## 4. Deployment

- **CI/CD**: GitHub Actions (`trading-bot.yml`) runs every 2 hours.
- **Dashboard**: GitHub Pages (`ihzaikrm.github.io/trading-bot`).
- **Telegram**: Listener runs every 5 minutes.

## 6. Signal Engine Package

The signal generation logic is now modularized under `modules/signal_engine/`:
- `analysts.py`: Individual LLM prompts for different roles.
- `consensus.py`: Weighted voting and aggregation.
- `confidence.py`: Calibration of confidence based on market conditions.
