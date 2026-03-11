import asyncio, json, os, sys, re, requests
from datetime import datetime
from collections import Counter
import ccxt
import pandas as pd

sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv()
from core.llm_clients import call_all_llms

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PAPER_FILE = "logs/paper_trades.json"

ASSETS = {
    "BTC/USDT": {"type": "crypto", "symbol": "BTC/USDT", "name": "Bitcoin"},
    "XAUUSD":   {"type": "stock",  "symbol": "GC=F",     "name": "Gold"},
    "SPX":      {"type": "stock",  "symbol": "^GSPC",    "name": "S&P 500"},
}

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"[TG] Gagal: {e}")

def load_trades():
    if os.path.exists(PAPER_FILE):
        with open(PAPER_FILE) as f:
            return json.load(f)
    return {"balance": 1000.0, "trades": [], "positions": {}, "shorts": {}}

def save_trades(data):
    os.makedirs("logs", exist_ok=True)
    with open(PAPER_FILE, "w") as f:
        json.dump(data, f, indent=2)

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

def get_crypto_mtf(symbol):
    ex = ccxt.gate()
    t = ex.fetch_ticker(symbol)
    price = round(float(t.get("last") or t.get("close") or 0), 2)
    change = round(float(t.get("percentage") or 0), 2)

    result = {"price": price, "change": change}
    for tf, limit in [("1d", 200), ("4h", 150), ("1h", 100)]:
        try:
            ohlcv = ex.fetch_ohlcv(symbol, tf, limit=limit)
            closes = [c[4] for c in ohlcv]
            ind = calc_indicators(closes)
            if ind:
                result[tf] = ind
        except Exception as e:
            print(f"    [{symbol} {tf}] Error: {e}")
    return result

def get_stock_mtf(symbol):
    import yfinance as yf
    result = {}

    # 1D timeframe
    try:
        hist_1d = yf.Ticker(symbol).history(period="1y", interval="1d")
        if not hist_1d.empty:
            price = round(float(hist_1d["Close"].iloc[-1]), 2)
            change = round((price - float(hist_1d["Close"].iloc[-2])) / float(hist_1d["Close"].iloc[-2]) * 100, 2)
            result["price"] = price
            result["change"] = change
            ind = calc_indicators(hist_1d["Close"].tolist())
            if ind:
                result["1d"] = ind
    except Exception as e:
        print(f"    [{symbol} 1d] Error: {e}")

    # 4H timeframe (resample dari 1H)
    try:
        hist_1h = yf.Ticker(symbol).history(period="60d", interval="1h")
        if not hist_1h.empty:
            # Resample ke 4H
            hist_4h = hist_1h["Close"].resample("4h").last().dropna()
            ind = calc_indicators(hist_4h.tolist())
            if ind:
                result["4h"] = ind
    except Exception as e:
        print(f"    [{symbol} 4h] Error: {e}")

    # 1H timeframe
    try:
        hist_1h = yf.Ticker(symbol).history(period="7d", interval="1h")
        if not hist_1h.empty:
            ind = calc_indicators(hist_1h["Close"].tolist())
            if ind:
                result["1h"] = ind
    except Exception as e:
        print(f"    [{symbol} 1h] Error: {e}")

    return result if "price" in result else None

def get_asset_data(name, info):
    try:
        if info["type"] == "crypto":
            return get_crypto_mtf(info["symbol"])
        else:
            return get_stock_mtf(info["symbol"])
    except Exception as e:
        print(f"  Error {name}: {e}")
        return None

def mtf_bias(data):
    """Hitung bias keseluruhan dari 3 timeframe"""
    scores = []
    for tf in ["1d", "4h", "1h"]:
        if tf not in data:
            continue
        ind = data[tf]
        score = 0
        # RSI
        if ind["rsi"] > 55: score += 1
        elif ind["rsi"] < 45: score -= 1
        # MACD
        if ind["macd_cross"] == "BULLISH": score += 1
        else: score -= 1
        # EMA
        if ind["ema_trend"] == "BULLISH": score += 1
        elif ind["ema_trend"] == "BEARISH": score -= 1
        # BB
        if ind["bb_pos"] == "OVERSOLD": score += 1
        elif ind["bb_pos"] == "OVERBOUGHT": score -= 1
        # StochRSI
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

    # Format prompt MTF
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

async def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=== MULTI-ASSET BOT (MTF + LONG/SHORT) | "+now+" ===")
    data = load_trades()
    positions = data.get("positions", {})
    shorts = data.get("shorts", {})

    # Cek circuit breaker
    initial = 1000.0
    current = data["balance"]
    for name, pos in positions.items():
        r = get_asset_data(name, ASSETS.get(name, {"type":"stock","symbol":name}))
        if r and "price" in r:
            current += pos["amount"] + (r["price"] - pos["entry_price"]) * pos["qty"]
    for name, pos in shorts.items():
        r = get_asset_data(name, ASSETS.get(name, {"type":"stock","symbol":name}))
        if r and "price" in r:
            current += pos["amount"] + (pos["entry_price"] - r["price"]) * pos["qty"]
    drawdown = max(0, (initial - current) / initial * 100)

    if drawdown > 3:
        msg = "⛔ CIRCUIT BREAKER: Drawdown "+str(round(drawdown,1))+"% > 3%!"
        print(msg); tg(msg)
        return

    alloc = data["balance"] / len(ASSETS)

    print("\nAnalisa 3 aset (MTF)...")
    summary = []
    for name, info in ASSETS.items():
        print(f"\n  [{name}] Mengambil data MTF...")
        asset_data = get_asset_data(name, info)
        if not asset_data or "price" not in asset_data:
            print(f"  {name}: gagal ambil data")
            continue

        price = asset_data["price"]
        change = asset_data["change"]
        bias = mtf_bias(asset_data)

        # Print ringkasan per TF
        for tf in ["1d", "4h", "1h"]:
            if tf in asset_data:
                ind = asset_data[tf]
                print(f"    {tf}: RSI:{ind['rsi']} | MACD:{ind['macd_cross']} | EMA:{ind['ema_trend']} | BB:{ind['bb_pos']}")
        print(f"    Bias MTF: {bias}")

        signal, conf, votes, details, bias = await get_signal(info["name"], asset_data)
        print(f"  -> {signal} conf:{conf} votes:{votes}")
        summary.append(f"{name}: {signal} ({conf}) [{bias}]")

        long_pos = positions.get(name)
        short_pos = shorts.get(name)

        # === OPEN LONG ===
        if signal == "BUY" and conf >= 0.55 and votes >= 3 and not long_pos and not short_pos and alloc > 10:
            qty = alloc / price
            positions[name] = {"entry_price": price, "qty": qty, "amount": alloc, "time": now}
            data["balance"] -= alloc
            msg = (f"🟢 BUY {info['name']}\n"
                   f"Harga: ${price} | 24h: {change}%\n"
                   f"Qty: {round(qty,6)} | Amount: ${round(alloc,2)}\n"
                   f"MTF Bias: {bias}\n"
                   f"Conf: {conf} ({votes} votes)\n\n"
                   + "\n".join(details))
            print(f"  [BUY] {name}")
            tg(msg)

        # === CLOSE LONG ===
        elif signal == "SELL" and long_pos:
            pnl = (price - long_pos["entry_price"]) * long_pos["qty"]
            data["balance"] += long_pos["amount"] + pnl
            data["trades"].append({**long_pos, "asset": name, "type": "long",
                                   "exit_price": price, "pnl": round(pnl,2), "exit_time": now})
            del positions[name]
            emoji = "✅" if pnl > 0 else "🔴"
            msg = (f"{emoji} SELL (Close Long) {info['name']}\n"
                   f"Entry: ${long_pos['entry_price']} | Exit: ${price}\n"
                   f"PnL: ${round(pnl,2)} | Balance: ${round(data['balance'],2)}")
            print(f"  [SELL] {name} PnL: ${round(pnl,2)}")
            tg(msg)

        # === OPEN SHORT ===
        elif signal == "SHORT" and conf >= 0.55 and votes >= 3 and not short_pos and not long_pos and alloc > 10:
            qty = alloc / price
            shorts[name] = {"entry_price": price, "qty": qty, "amount": alloc, "time": now}
            data["balance"] -= alloc
            msg = (f"🔴 SHORT {info['name']}\n"
                   f"Harga: ${price} | 24h: {change}%\n"
                   f"Qty: {round(qty,6)} | Amount: ${round(alloc,2)}\n"
                   f"MTF Bias: {bias}\n"
                   f"Conf: {conf} ({votes} votes)\n\n"
                   + "\n".join(details))
            print(f"  [SHORT] {name}")
            tg(msg)

        # === CLOSE SHORT ===
        elif signal == "COVER" and short_pos:
            pnl = (short_pos["entry_price"] - price) * short_pos["qty"]
            data["balance"] += short_pos["amount"] + pnl
            data["trades"].append({**short_pos, "asset": name, "type": "short",
                                   "exit_price": price, "pnl": round(pnl,2), "exit_time": now})
            del shorts[name]
            emoji = "✅" if pnl > 0 else "🔴"
            msg = (f"{emoji} COVER (Close Short) {info['name']}\n"
                   f"Entry: ${short_pos['entry_price']} | Exit: ${price}\n"
                   f"PnL: ${round(pnl,2)} | Balance: ${round(data['balance'],2)}")
            print(f"  [COVER] {name} PnL: ${round(pnl,2)}")
            tg(msg)

    data["positions"] = positions
    data["shorts"] = shorts
    save_trades(data)

    # Status ringkasan
    trades = data["trades"]
    wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    winrate = str(round(wins/len(trades)*100))+"%" if trades else "N/A"
    total_pnl = sum(t.get("pnl",0) for t in trades)
    open_long = ", ".join(positions.keys()) if positions else "Tidak ada"
    open_short = ", ".join(shorts.keys()) if shorts else "Tidak ada"

    status = (f"📊 MULTI-ASSET STATUS {now}\n"
              f"Balance: ${round(data['balance'],2)}\n"
              f"Drawdown: {round(drawdown,1)}%\n"
              f"Long: {open_long}\n"
              f"Short: {open_short}\n\n"
              + "\n".join(summary) + "\n\n"
              f"Trade: {len(trades)} | Winrate: {winrate}\n"
              f"Total PnL: ${round(total_pnl,2)}")
    print("\n"+status)
    tg(status)
    print("\n=== SELESAI ===")

asyncio.run(main())