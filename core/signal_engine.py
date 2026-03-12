# core/signal_engine.py
import json, re
from collections import Counter
from .llm_clients import call_all_llms
from .llm_performance import get_weights, add_prediction

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

def rule_based_signal(data):
    """Fallback jika semua LLM gagal"""
    bias = mtf_bias(data)
    if bias in ["STRONG_BULL", "BULL"]:
        return "BUY", 0.6
    elif bias in ["STRONG_BEAR", "BEAR"]:
        return "SHORT", 0.6
    else:
        return "HOLD", 0.5

async def get_signal(asset_name, data, timestamp, perf):
    price = data["price"]
    change = data["change"]
    tf_lines = []
    for tf, label in [("1d", "Daily"), ("4h", "4-Hour"), ("1h", "1-Hour")]:
        if tf in data:
            ind = data[tf]
            tf_lines.append(
                f"[{label}] RSI:{ind['rsi']} | MACD:{ind['macd_cross']}({ind['macd_hist']}) | "
                f"EMA:{ind['ema_trend']} | BB:{ind['bb_pos']} | StochRSI:{ind['stoch_rsi']}({ind['stoch_signal']})"
            )

    bias = mtf_bias(data)
    prompt = (
        f"{asset_name} | Harga: {price} | 24h: {change}%\n"
        f"MTF Bias: {bias}\n"
        + "\n".join(tf_lines) + "\n\n"
        'Balas JSON: {"signal":"BUY/SELL/SHORT/COVER/HOLD","confidence":0.5,"reason":"singkat"}\n'
        "BUY=buka long, SELL=tutup long, SHORT=buka short, COVER=tutup short, HOLD=tidak ada aksi"
    )

    results = await call_all_llms(
        "Analis trading profesional multi-timeframe. Gunakan bias MTF untuk keputusan. Balas JSON saja.", prompt)

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
                    # Catat prediksi jika entry
                    if sig in ["BUY","SHORT"]:
                        add_prediction(asset_name, timestamp, price, llm, sig, conf)
            except:
                pass

    if not details:
        # Fallback ke rule-based jika semua LLM gagal
        fallback_signal, fallback_conf = rule_based_signal(data)
        return fallback_signal, fallback_conf, 0, ["Fallback: rule-based"], bias

    best_signal = max(score.items(), key=lambda x: x[1])[0]
    total_weight = sum(weights.values())
    conf = score[best_signal] / total_weight if total_weight > 0 else 0.5
    # Hitung jumlah LLM yang memberikan sinyal yang sama (untuk info)
    votes = sum(1 for d in details if best_signal in d)
    return best_signal, round(conf, 2), votes, details, bias