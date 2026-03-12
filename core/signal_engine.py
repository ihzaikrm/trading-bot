# core/signal_engine.py
import json, re
from collections import Counter
from .llm_clients import call_all_llms

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

async def get_signal(name, data):
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
        f"{name} | Harga: {price} | 24h: {change}%\n"
        f"MTF Bias: {bias}\n"
        + "\n".join(tf_lines) + "\n\n"
        'Balas JSON: {"signal":"BUY/SELL/SHORT/COVER/HOLD","confidence":0.5,"reason":"singkat"}\n'
        "BUY=buka long, SELL=tutup long, SHORT=buka short, COVER=tutup short, HOLD=tidak ada aksi"
    )

    results = await call_all_llms(
        "Analis trading profesional multi-timeframe. Gunakan bias MTF untuk keputusan. Balas JSON saja.", prompt)

    signals, confs, details = [], [], []
    for llm, (ok, resp) in results.items():
        if ok:
            try:
                r = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group())
                sig = r["signal"].upper()
                if sig in ["BUY","SELL","SHORT","COVER","HOLD"]:
                    signals.append(sig)
                    confs.append(r.get("confidence", 0.5))
                    details.append(f"{llm}: {sig} ({round(r.get('confidence',0.5)*100)}%)")
            except: pass

    if not signals:
        return "HOLD", 0.5, 0, [], bias
    most = Counter(signals).most_common(1)[0]
    return most[0], round(sum(confs)/len(confs),2), most[1], details, bias