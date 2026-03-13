# core/signal_engine.py
import json, re
import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime
from .llm_clients import call_all_llms
from .llm_performance import get_weights, add_prediction
from .news_sentiment import get_news_sentiment, get_fear_greed
from config.trading_params import USE_NEWS_SENTIMENT, USE_FEAR_GREED
from core.alternative_data import get_alt_data_for_prompt

# ----------------------------------------------------------------------
# Strategi final per aset
# ----------------------------------------------------------------------

def _sig_btc_vol_tsmom(ind, closes, volumes):
    if len(closes) < 30 or len(volumes) < 20:
        return "HOLD"
    ret_30d = (closes[-1] - closes[-30]) / closes[-30]
    ret_7d  = (closes[-1] - closes[-7])  / closes[-7]
    vol_ratio = volumes[-1] / (np.median(volumes[-20:]) + 1e-9)
    vol_strong = vol_ratio > 1.2
    score = 0
    if ret_30d > 0:   score += 2
    elif ret_30d < 0: score -= 2
    if ret_7d > 0:    score += 1
    elif ret_7d < 0:  score -= 1
    if ind["ema_trend"] == "BULLISH":  score += 2
    elif ind["ema_trend"] == "BEARISH": score -= 2
    if ind["macd_cross"] == "BULLISH": score += 1
    else: score -= 1
    if vol_strong: score += 2
    if score >= 5:
        return "BUY"
    return "HOLD"

def _sig_gold_smart_hold(ind, closes, date=None):
    if len(closes) < 200:
        return "HOLD"
    if date is not None:
        ts = pd.Timestamp(date)
        if ts.month in [3,4,5,6]:
            return "HOLD"
        if ts.weekday() == 0:
            return "HOLD"
    s = pd.Series(closes)
    ema50  = float(s.ewm(span=50).mean().iloc[-1])
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]
    ret_3m = (closes[-1] - closes[-63]) / closes[-63] if len(closes) >= 63 else 0
    ret_1m = (closes[-1] - closes[-21]) / closes[-21] if len(closes) >= 21 else 0
    if ret_3m < -0.08 and ret_1m < -0.03:
        return "HOLD"
    conditions = sum([
        price > ema200,
        ema50 > ema200,
        ret_3m > 0.03,
        ret_1m > 0,
        ind["ema_trend"] == "BULLISH",
        ind["macd_cross"] == "BULLISH",
    ])
    if conditions >= 5:
        return "BUY"
    return "HOLD"

def _sig_spx_monthly_seasonal(ind, closes, date):
    if len(closes) < 21:
        return "HOLD"
    month = pd.Timestamp(date).month
    if month in [6, 9]:
        return "HOLD"
    STRONG = [1,4,7,11]
    score = 0
    high20 = max(closes[-21:-1])
    if closes[-1] > high20:            score += 3
    if ind["ema_trend"] == "BULLISH":  score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if ind["rsi"] > 50:                score += 1
    if month in STRONG:                score += 1
    if score >= 5:
        return "BUY"
    return "HOLD"

ASSET_STRATEGY_MAP = {
    "BTC/USDT": _sig_btc_vol_tsmom,
    "GC=F":     _sig_gold_smart_hold,
    "^GSPC":    _sig_spx_monthly_seasonal,
}

def get_strategy_status_text():
    from config.assets import ASSETS
    lines = ["📊 *STRATEGI YANG DIGUNAKAN*"]
    for name, info in ASSETS.items():
        symbol = info["symbol"]
        if symbol == "BTC/USDT":
            lines.append(f"{name} → Vol-Weighted TSMOM (R2) | Score 8/14")
        elif symbol == "GC=F":
            lines.append(f"{name} → Smart Hold (Academic) | Exit saat prolonged bear")
        elif symbol == "^GSPC":
            lines.append(f"{name} → Monthly Seasonal R8 | Score 7/14 | Skip Jun, Sep")
        else:
            lines.append(f"{name} → Rule-based fallback")
    return "\n".join(lines)

def mtf_bias(data):
    scores = []
    for tf in ["1d", "4h", "1h"]:
        if tf not in data:
            continue
        ind = data[tf]
        score = 0
        if ind["rsi"] > 55: score += 1
        elif ind["rsi"] < 45: score -= 1
        if ind["macd_cross"] == "BULLISH": score += 1
        else: score -= 1
        if ind["ema_trend"] == "BULLISH": score += 1
        elif ind["ema_trend"] == "BEARISH": score -= 1
        if ind["bb_pos"] == "OVERSOLD": score += 1
        elif ind["bb_pos"] == "OVERBOUGHT": score -= 1
        if ind["stoch_signal"] == "OVERSOLD": score += 1
        elif ind["stoch_signal"] == "OVERBOUGHT": score -= 1
        scores.append(score)
    if not scores:
        return "NEUTRAL"
    avg = sum(scores) / len(scores)
    if avg >= 1.5: return "STRONG_BULL"
    elif avg >= 0.5: return "BULL"
    elif avg <= -1.5: return "STRONG_BEAR"
    elif avg <= -0.5: return "BEAR"
    else: return "NEUTRAL"

def rule_based_signal_v2(asset_name, ind, closes, volumes, date):
    from config.assets import ASSETS
    symbol = None
    for name, info in ASSETS.items():
        if name == asset_name:
            symbol = info["symbol"]
            break
    if symbol is None:
        return "HOLD", 0.5
    if symbol in ASSET_STRATEGY_MAP:
        strat_func = ASSET_STRATEGY_MAP[symbol]
        if 'date' in strat_func.__code__.co_varnames:
            signal = strat_func(ind, closes, date)
        else:
            signal = strat_func(ind, closes, volumes)
        confidence = 0.7 if signal != "HOLD" else 0.5
        return signal, confidence
    else:
        bias = mtf_bias({"1d": ind})
        if bias in ["STRONG_BULL", "BULL"]:
            return "BUY", 0.6
        elif bias in ["STRONG_BEAR", "BEAR"]:
            return "SHORT", 0.6
        else:
            return "HOLD", 0.5

async def get_signal(asset_name, data, timestamp, perf, closes=None, volumes=None):
    price = data["price"]
    change = data["change"]
    date_str = timestamp.split()[0]

    if closes is None:
        closes = data.get("closes", [])
    if volumes is None:
        volumes = data.get("volumes", [])

    news = {}
    fng = {}
    if USE_NEWS_SENTIMENT:
        news = get_news_sentiment(asset_name)
    if USE_FEAR_GREED:
        fng = get_fear_greed()

    tf_lines = []
    for tf, label in [("1d", "Daily"), ("4h", "4-Hour"), ("1h", "1-Hour")]:
        if tf in data:
            ind = data[tf]
            tf_lines.append(
                f"[{label}] RSI:{ind['rsi']} | MACD:{ind['macd_cross']}({ind['macd_hist']}) | "
                f"EMA:{ind['ema_trend']} | BB:{ind['bb_pos']} | StochRSI:{ind['stoch_rsi']}({ind['stoch_signal']})"
            )

    bias = mtf_bias(data)

    # D4: Skip LLM jika MTF NEUTRAL
    if bias == "NEUTRAL":
        fallback_signal, fallback_conf = rule_based_signal_v2(
            asset_name, data.get("1d", {}), closes, volumes, date_str
        )
        return fallback_signal, fallback_conf, 0, ["D4: MTF NEUTRAL - rule-based only"], bias
    extra_info = ""
    # H5: Alternative data
    alt_data = get_alt_data_for_prompt(asset_name)
    if alt_data:
        extra_info += f"\n{alt_data}"
    if news:
        extra_info += f"\nNews Sentiment: {news['sentiment']} (skor {news['score']}, {news['articles']} artikel)"
    if fng:
        extra_info += f"\nFear & Greed Index: {fng['value']} - {fng['classification']}"

    prompt = (
        f"{asset_name} | Harga: {price} | 24h: {change}%\n"
        f"MTF Bias: {bias}{extra_info}\n"
        + "\n".join(tf_lines) + "\n\n"
        'Balas JSON: {"signal":"BUY/SELL/SHORT/COVER/HOLD","confidence":0.5,"reason":"singkat"}\n'
        "BUY=buka long, SELL=tutup long, SHORT=buka short, COVER=tutup short, HOLD=tidak ada aksi"
    )

    results = await call_all_llms(
        "Analis trading profesional multi-timeframe. Gunakan bias MTF dan sentimen untuk keputusan. Balas JSON saja.", prompt)

    weights = get_weights(perf)
    score = {"BUY":0, "SELL":0, "SHORT":0, "COVER":0, "HOLD":0}
    details = []
    for llm, (ok, resp) in results.items():
        if ok:
            try:
                r = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group())
                sig = r["signal"].upper()
                if sig in score:
                    conf = r.get("confidence", 0.5)
                    weight = weights.get(llm, 0.1)
                    score[sig] += weight * conf
                    details.append(f"{llm}: {sig} ({round(conf*100)}%)")
                    if sig in ["BUY","SHORT"]:
                        add_prediction(asset_name, timestamp, price, llm, sig, conf)
            except:
                pass

    if not details:
        fallback_signal, fallback_conf = rule_based_signal_v2(asset_name, data.get("1d", {}), closes, volumes, date_str)
        return fallback_signal, fallback_conf, 0, ["Fallback: strategi final"], bias

    best_signal = max(score.items(), key=lambda x: x[1])[0]
    total_weight = sum(weights.values())
    conf = score[best_signal] / total_weight if total_weight > 0 else 0.5
    votes = sum(1 for d in details if best_signal in d)
    return best_signal, round(conf, 2), votes, details, bias
