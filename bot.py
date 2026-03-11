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

# Daftar semua aset
ASSETS = {
    "BTC/USDT":  {"type": "crypto", "symbol": "BTC/USDT"},
    "ETH/USDT":  {"type": "crypto", "symbol": "ETH/USDT"},
    "BNB/USDT":  {"type": "crypto", "symbol": "BNB/USDT"},
    "SOL/USDT":  {"type": "crypto", "symbol": "SOL/USDT"},
    "QQQ":       {"type": "stock",  "symbol": "QQQ"},
    "SPX":       {"type": "stock",  "symbol": "^GSPC"},
    "XAUUSD":    {"type": "stock",  "symbol": "GC=F"},
    "EURUSD":    {"type": "forex",  "symbol": "EUR/USD"},
    "USDJPY":    {"type": "forex",  "symbol": "USD/JPY"},
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
    return {"balance": 1000.0, "trades": [], "positions": {}}

def save_trades(data):
    os.makedirs("logs", exist_ok=True)
    with open(PAPER_FILE, "w") as f:
        json.dump(data, f, indent=2)

def calc_indicators(closes, volumes=None):
    s = pd.Series(closes)
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
    macd_val = round(float(macd.iloc[-1]), 4)
    macd_sig = round(float(signal.iloc[-1]), 4)
    macd_hist = round(macd_val - macd_sig, 4)
    macd_cross = "BULLISH" if macd_val > macd_sig else "BEARISH"
    return rsi, macd_val, macd_sig, macd_hist, macd_cross

def get_crypto_data(symbol):
    ex = ccxt.gate()
    t = ex.fetch_ticker(symbol)
    price = float(t.get("last") or t.get("close") or 0)
    change = float(t.get("percentage") or 0)
    ohlcv = ex.fetch_ohlcv(symbol, "1d", limit=50)
    closes = [c[4] for c in ohlcv]
    volumes = [c[5] for c in ohlcv]
    vol_avg = sum(volumes[-10:]) / 10
    vol_now = volumes[-1]
    vol_ratio = round(vol_now / vol_avg, 2) if vol_avg > 0 else 1
    rsi, macd, macd_sig, macd_hist, macd_cross = calc_indicators(closes)
    return price, change, rsi, macd, macd_hist, macd_cross, vol_ratio

def get_stock_data(symbol):
    import yfinance as yf
    t = yf.Ticker(symbol)
    hist = t.history(period="60d")
    if hist.empty:
        return None
    price = round(float(hist["Close"].iloc[-1]), 2)
    prev = float(hist["Close"].iloc[-2])
    change = round((price - prev) / prev * 100, 2)
    closes = hist["Close"].tolist()
    volumes = hist["Volume"].tolist()
    vol_avg = sum(volumes[-10:]) / 10
    vol_ratio = round(volumes[-1] / vol_avg, 2) if vol_avg > 0 else 1
    rsi, macd, macd_sig, macd_hist, macd_cross = calc_indicators(closes)
    return price, change, rsi, macd, macd_hist, macd_cross, vol_ratio

def get_forex_data(pair):
    base, quote = pair.split("/")
    try:
        r = requests.get(f"https://api.frankfurter.app/latest?from={base}&to={quote}", timeout=10)
        data = r.json()
        price = round(data["rates"][quote], 5)
        # Forex: ambil history dari yfinance
        import yfinance as yf
        sym = base+quote+"=X"
        hist = yf.Ticker(sym).history(period="60d")
        if hist.empty:
            return price, 0, 50, 0, 0, "NEUTRAL", 1
        closes = hist["Close"].tolist()
        prev = closes[-2] if len(closes) > 1 else price
        change = round((price - prev) / prev * 100, 2)
        rsi, macd, macd_sig, macd_hist, macd_cross = calc_indicators(closes)
        return price, change, rsi, macd, macd_hist, macd_cross, 1
    except:
        return None

def get_asset_data(name, info):
    try:
        if info["type"] == "crypto":
            return get_crypto_data(info["symbol"])
        elif info["type"] == "stock":
            return get_stock_data(info["symbol"])
        elif info["type"] == "forex":
            return get_forex_data(info["symbol"])
    except Exception as e:
        print(f"  Error {name}: {e}")
        return None

def score_asset(rsi, macd_hist, macd_cross, vol_ratio, change):
    score = 0
    # RSI score
    if rsi < 35: score += 3
    elif rsi < 45: score += 2
    elif rsi < 55: score += 1
    elif rsi > 70: score -= 2
    # MACD score
    if macd_cross == "BULLISH": score += 2
    if macd_hist > 0: score += 1
    # Volume score
    if vol_ratio > 1.5: score += 1
    # Momentum score
    if change > 1: score += 1
    elif change < -3: score -= 1
    return score

async def get_signal(name, price, change, rsi, macd_hist, macd_cross, vol_ratio):
    prompt = (name+" Price: "+str(price)+" | 24h: "+str(change)+"%\n"
             "RSI: "+str(rsi)+" | MACD Hist: "+str(macd_hist)+" ("+macd_cross+")\n"
             "Volume Ratio: "+str(vol_ratio)+"x vs avg\n"
             'Balas JSON: {"signal":"BUY/SELL/HOLD","confidence":0.5,"reason":"singkat"}')
    results = await call_all_llms("Analis trading. Balas JSON saja.", prompt)
    signals, confs, details = [], [], []
    for llm, (ok, resp) in results.items():
        if ok:
            try:
                r = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group())
                signals.append(r["signal"])
                confs.append(r.get("confidence", 0.5))
                details.append(llm+": "+r["signal"]+" ("+str(round(r.get("confidence",0.5)*100))+"%)")
            except: pass
    if not signals:
        return "HOLD", 0.5, 0, []
    most = Counter(signals).most_common(1)[0]
    return most[0], round(sum(confs)/len(confs),2), most[1], details

async def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=== MULTI-ASSET BOT | "+now+" ===")
    data = load_trades()
    positions = data.get("positions", {})

    # Step 1: Scan semua aset
    print("\n[1] Scanning "+str(len(ASSETS))+" aset...")
    asset_data = {}
    scores = {}
    for name, info in ASSETS.items():
        result = get_asset_data(name, info)
        if result:
            price, change, rsi, macd, macd_hist, macd_cross, vol_ratio = result
            asset_data[name] = (price, change, rsi, macd, macd_hist, macd_cross, vol_ratio)
            scores[name] = score_asset(rsi, macd_hist, macd_cross, vol_ratio, change)
            print(f"  {name}: ${price} | RSI:{rsi} | MACD:{macd_cross} | Score:{scores[name]}")

    # Step 2: Pilih 3 aset terkuat
    top3 = sorted(scores, key=scores.get, reverse=True)[:3]
    print("\n[2] Top 3 aset: "+", ".join(top3))
    tg("SCAN SELESAI "+now+"\nTop 3 aset:\n"+"\n".join([n+" (score:"+str(scores[n])+")" for n in top3]))

    # Step 3: Analisa LLM untuk top 3
    print("\n[3] Analisa LLM untuk top 3...")
    initial = 1000.0
    current_value = data["balance"]
    for name, pos in positions.items():
        if name in asset_data:
            price = asset_data[name][0]
            current_value += pos["amount"] + (price - pos["entry_price"]) * pos["qty"]
    drawdown = max(0, (initial - current_value) / initial * 100)

    if drawdown > 5:
        msg = "CIRCUIT BREAKER: Drawdown "+str(round(drawdown,1))+"% > 5%!"
        print(msg); tg(msg)
        return

    alloc = data["balance"] / 3  # Modal dibagi 3

    for name in top3:
        price, change, rsi, macd, macd_hist, macd_cross, vol_ratio = asset_data[name]
        signal, conf, votes, details = await get_signal(name, price, change, rsi, macd_hist, macd_cross, vol_ratio)
        pos = positions.get(name)
        print(f"  {name}: {signal} conf:{conf} votes:{votes}")

        if signal == "BUY" and conf >= 0.6 and not pos and alloc > 10:
            qty = alloc / price
            positions[name] = {"entry_price": price, "qty": qty, "amount": alloc, "time": now}
            data["balance"] -= alloc
            msg = ("BUY "+name+"\nHarga: "+str(price)+"\nQty: "+str(round(qty,6))+"\nAmount: $"+str(round(alloc,2))
                   +"\nRSI: "+str(rsi)+" | MACD: "+macd_cross+"\nConf: "+str(conf)+" ("+str(votes)+" votes)"
                   +"\n\n"+"\n".join(details))
            tg(msg)

        elif signal == "SELL" and pos:
            pnl = (price - pos["entry_price"]) * pos["qty"]
            data["balance"] += pos["amount"] + pnl
            data["trades"].append({**pos, "asset": name, "exit_price": price, "pnl": round(pnl,2), "exit_time": now})
            del positions[name]
            msg = ("SELL "+name+"\nEntry: "+str(pos["entry_price"])+"\nExit: "+str(price)
                   +"\nPnL: $"+str(round(pnl,2))+"\nBalance: $"+str(round(data["balance"],2)))
            tg(msg)

    data["positions"] = positions
    save_trades(data)

    # Step 4: Status
    trades = data["trades"]
    wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    winrate = str(round(wins/len(trades)*100))+"%" if trades else "N/A"
    total_pnl = sum(t.get("pnl",0) for t in trades)
    open_pos = ", ".join(positions.keys()) if positions else "Tidak ada"

    status = ("MULTI-ASSET STATUS "+now
             +"\nBalance: $"+str(round(data["balance"],2))
             +"\nDrawdown: "+str(round(drawdown,1))+"%"
             +"\nPosisi: "+open_pos
             +"\nTop 3: "+", ".join(top3)
             +"\nTotal Trade: "+str(len(trades))+" | Winrate: "+winrate
             +"\nTotal PnL: $"+str(round(total_pnl,2)))
    print("\n"+status)
    tg(status)
    print("=== SELESAI ===")

asyncio.run(main())
