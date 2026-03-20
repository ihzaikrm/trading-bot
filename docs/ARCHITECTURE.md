# Synclavix – Architecture Overview

## 1. High‑Level Flow

[Market Data & News]
         ↓
    DXY Filter → penalty confidence
         ↓
 Momentum Filter → skip LLM if BEARISH
         ↓
   SMC + Delta → context for LLM
         ↓
   6 LLM Council → voting & dynamic weighting
         ↓
   Execution (per asset, with Kelly sizing)

## 2. Core Modules

| Module | File | Description |
|--------|------|-------------|
| **DXY Filter** | core/dxy_filter.py | Fetches DXY via yfinance. Returns BULLISH/BEARISH/NEUTRAL; penalty 0.15 if BEARISH. |
| **Momentum Filter** | core/momentum_filter.py | Strategy E: RSI 45‑65 + MACD cross + EMA50>EMA200 + cumulative delta lookback 3. Pre‑filter before LLM. |
| **SMC Context** | core/smc_context.py | Detects Order Blocks, Fair Value Gaps, Liquidity Sweep. Adds context to LLM prompt. |
| **Screener** | core/screener.py | Multi‑asset scanning (crypto + stocks/ETFs) with manipulation firewall, dynamic Kelly caps. Outputs ACTIVE_ASSETS. |
| **Narrative Scanner** | core/narrative_scanner.py | Keyword scoring + LLM voting → active narratives. Falls back to keyword scores if LLM fails. |
| **LLM Clients** | core/llm_clients.py | Wrapper for OpenRouter (6 models: Qwen, DeepSeek, Claude, GPT, Grok, Gemini). |
| **Dynamic Weights** | core/dynamic_weights.py | ELO + win‑rate + profit → per‑LLM weight. |
| **Portfolio Manager** | core/portfolio_manager.py | Tracks positions, applies trailing stop, partial TP, risk limits. |
| **Performance Boost** | core/performance_boost.py | Fear & Greed, VIX regime, Kelly multiplier, circuit breaker. |
| **Cot Weekly** | core/cot_weekly.py | Weekly self‑evaluation and Telegram report. |

## 3. Execution Flow (per cycle, every 2h)

1. **Data Fetch**  
   - Crypto prices & indicators via CryptoCompare, yfinance.  
   - News multi‑timeframe (NewsAPI + RSS).  
   - Fear & Greed, VIX.

2. **Filter Chain**  
   - DXY filter → adjust confidence (penalty 0.15 if BEARISH).  
   - Momentum filter → if BEARISH → skip LLM for that asset (hold position).  
   - SMC + Delta → generate context string for LLM.

3. **Narrative Scan**  
   - Keyword scoring → rank top 3 narratives.  
   - LLM voting (if available) → final narrative list.  
   - Map narratives to asset classes & allocate portfolio weights.

4. **LLM Council**  
   - For each active asset, build prompt (technicals + news + SMC context).  
   - Call all 6 LLMs, collect BUY/SELL/HOLD and confidence.  
   - Weighted voting using dynamic weights → final signal & confidence.

5. **Risk & Execution**  
   - Kelly sizing: size = balance * kelly_mult * confidence * 0.3 (capped per asset class).  
   - Check circuit breaker (drawdown >5% → halt).  
   - Execute trades via exchange API (Gate.io).

6. **Logging & Reporting**  
   - Update paper_trades.json with full decision context.  
   - Send Telegram status.  
   - Record LLM performance for weight updates.

## 4. Key Parameters (see config/trading_params.py)

| Parameter | Value | Source |
|-----------|-------|--------|
| RSI entry range | 45–65 | Backtest optimisation |
| Trailing stop | 20% | Grid search |
| Delta lookback | 3 days | Grid search |
| DXY penalty | 0.15 | Historical correlation |
| Kelly base | 0.3 × confidence × VIX_mult | Literature |
| Circuit breaker | 5% drawdown | Risk policy |

## 5. Deployment

- **CI/CD**: GitHub Actions (	rading-bot.yml runs every 2 hours).  
- **Dashboard**: GitHub Pages (ihzaikrm.github.io/trading-bot).  
- **Telegram**: Listener runs every 5 minutes.
