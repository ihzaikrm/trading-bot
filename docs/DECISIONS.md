# Synclavix – Design Decisions

## 1. Why RSI 45–65 (not oversold)?

Backtest 5 years (2000+ days) showed that buying at RSI < 35 generated very few signals in trending markets.  
Using momentum zone (45–65) captured the start of uptrends, increasing win rate from 15% to 50% (combined with other filters).  
[See acktest.py and grid search results.]

## 2. Why Trailing Stop 20%?

Trailing stop 20% gave the highest profit in the 5‑year backtest (Strategy E, +69.75%).  
Lower stops (15%) exited too early; higher stops (25%) increased drawdown.  
Monte Carlo showed worst‑case drawdown 20% with this setting.

## 3. Why Delta Lookback 3 Days?

Cumulative delta approximates buying pressure. Lookback 3 days gave best results in grid search.  
Shorter (1‑2 days) increased noise; longer (7‑10 days) delayed response to trend changes.

## 4. Why 6 LLM Models?

- **Qwen, DeepSeek**: Strong reasoning, open‑source alternatives.  
- **Claude, GPT, Gemini, Grok**: Diverse closed‑source perspectives.  
- Adversarial voting reduces bias; dynamic weighting (ELO + win‑rate) improves over time.  
- Cost: ~/month via OpenRouter with crypto deposit.

## 5. Why Multi‑Asset Screener?

- Diversifies across crypto, equities, commodities, ETFs.  
- Manipulation firewall protects against pump‑and‑dump.  
- Dynamic position caps (by market cap) align risk with liquidity.  
- Integration with narratives ensures thematic alignment.

## 6. Why DXY Filter?

DXY has negative correlation with BTC (and risk assets). Penalising confidence when DXY is strong reduces exposure during dollar rallies.  
Correlation validated by academic literature and backtest (lower drawdown).

## 7. Why Circuit Breaker 5%?

Limits maximum daily loss, prevents catastrophic drawdown.  
Chosen based on risk policy “capital preservation first”.  
Adjustable based on market regime (VIX) but hard limit at 5%.

## 8. Why Open Source Core but Closed‑Source Strategy?

- **Open source**: contracts, guardian module, governance → builds trust.  
- **Closed source**: parameter optimisation, proprietary prompts, dynamic weights → protects alpha.  
- Model inspired by Ethereum Foundation (open protocol) + proprietary trading strategies.

## 9. Why Hybrid Node Roles?

- Light nodes: accessible to everyone (caching, monitoring).  
- Edge nodes: medium hardware, preprocessing.  
- Full nodes: GPU‑heavy, participate in consensus.  
- Incentives proportional to contribution, with non‑monetary rewards to keep light nodes engaged.  
- Prevents centralisation while maintaining performance.

## 10. Why Gradual Anonymity?

- Stage 0 (research): normal identity okay.  
- Stage 1 (public launch): switch to full anonymity (VPN, separate accounts, dedicated hardware).  
- Stage 2 (community): maintain anonymous persona; use offshore structure for funds.  
- Inspired by Satoshi Nakamoto – identity irrelevant if code and mission stand alone.

## 11. Why Monte Carlo for Stress Test?

- Traditional backtest assumes historical order of trades; Monte Carlo randomises sequence to test robustness.  
- Strategy E showed 100% profitability across 1000 random sequences → confirms resilience.

## 12. Why Kelly with VIX Adjustment?

- Kelly criterion optimises growth but is aggressive.  
- Reducing Kelly multiplier when VIX high (fear/panic) keeps risk manageable.  
- Empirical data: higher VIX leads to wider drawdowns; scaling position size prevents ruin.
