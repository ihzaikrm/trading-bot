# core/indicators.py
import pandas as pd

def calc_indicators(closes):
    s = pd.Series(closes)
    if len(s) < 26:
        return None

    # RSI
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss.replace(0, 1)
    rsi = round(float((100 - 100/(1+rs)).iloc[-1]), 2)

    # MACD
    ema12 = s.ewm(span=12).mean()
    ema26 = s.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    macd_hist = round(float((macd - signal).iloc[-1]), 4)
    macd_cross = "BULLISH" if macd.iloc[-1] > signal.iloc[-1] else "BEARISH"

    # EMA
    ema20 = round(float(s.ewm(span=20).mean().iloc[-1]), 2)
    ema50 = round(float(s.ewm(span=min(50, len(s))).mean().iloc[-1]), 2)
    ema200 = round(float(s.ewm(span=min(200, len(s))).mean().iloc[-1]), 2)
    price_now = float(s.iloc[-1])
    ema_trend = "BULLISH" if price_now > ema20 > ema50 else ("BEARISH" if price_now < ema20 < ema50 else "MIXED")

    # Bollinger Bands
    bb_mid = s.rolling(20).mean()
    bb_std = s.rolling(20).std()
    bb_upper = round(float((bb_mid + 2*bb_std).iloc[-1]), 2)
    bb_lower = round(float((bb_mid - 2*bb_std).iloc[-1]), 2)
    if price_now >= bb_upper:
        bb_pos = "OVERBOUGHT"
    elif price_now <= bb_lower:
        bb_pos = "OVERSOLD"
    else:
        bb_pos = "MIDDLE"

    # Stochastic RSI
    rsi_series = 100 - 100/(1 + gain/loss.replace(0,1))
    stoch_min = rsi_series.rolling(14).min()
    stoch_max = rsi_series.rolling(14).max()
    stoch_rsi = round(float(((rsi_series - stoch_min)/(stoch_max - stoch_min + 1e-10)).iloc[-1] * 100), 2)
    stoch_signal = "OVERBOUGHT" if stoch_rsi > 80 else ("OVERSOLD" if stoch_rsi < 20 else "NEUTRAL")

    return {
        "rsi": rsi, "macd_hist": macd_hist, "macd_cross": macd_cross,
        "ema20": ema20, "ema50": ema50, "ema200": ema200, "ema_trend": ema_trend,
        "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_pos": bb_pos,
        "stoch_rsi": stoch_rsi, "stoch_signal": stoch_signal
    }