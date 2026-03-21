# core/market_data.py
import ccxt
import yfinance as yf
import asyncio
from datetime import datetime
from .indicators import calc_indicators

def is_market_open(asset_type):
    now = datetime.utcnow()
    if asset_type == "crypto":
        return True
    if now.weekday() >= 5:
        return False
    return True

async def get_crypto_mtf(symbol):
    loop = asyncio.get_event_loop()
    ex = ccxt.gate()
    t = await loop.run_in_executor(None, lambda: ex.fetch_ticker(symbol))
    price = round(float(t.get("last") or t.get("close") or 0), 2)
    change = round(float(t.get("percentage") or 0), 2)

    result = {"price": price, "change": change, "closes": [], "volumes": []}
    for tf, limit in [("1d", 200), ("4h", 150), ("1h", 100)]:
        try:
            ohlcv = await loop.run_in_executor(None, lambda: ex.fetch_ohlcv(symbol, tf, limit=limit))
            closes = [c[4] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]
            ind = calc_indicators(closes)
            if ind:
                result[tf] = ind
                if tf == "1d":
                    result["closes"] = closes
                    result["volumes"] = volumes
        except Exception as e:
            print(f"    [{symbol} {tf}] Error: {e}")
    return result

async def get_stock_mtf(symbol):
    loop = asyncio.get_event_loop()
    result = {"closes": [], "volumes": []}
    try:
        hist_1d = await loop.run_in_executor(None, lambda: yf.Ticker(symbol).history(period="1y", interval="1d"))
        if not hist_1d.empty:
            price = round(float(hist_1d["Close"].iloc[-1]), 2)
            change = round((price - float(hist_1d["Close"].iloc[-2])) / float(hist_1d["Close"].iloc[-2]) * 100, 2)
            result["price"] = price
            result["change"] = change
            closes = hist_1d["Close"].tolist()
            volumes = hist_1d["Volume"].tolist() if "Volume" in hist_1d else []
            ind = calc_indicators(closes)
            if ind:
                result["1d"] = ind
                result["closes"] = closes
                result["volumes"] = volumes
    except Exception as e:
        print(f"    [{symbol} 1d] Error: {e}")

    try:
        hist_1h = await loop.run_in_executor(None, lambda: yf.Ticker(symbol).history(period="60d", interval="1h"))
        if not hist_1h.empty:
            hist_4h = hist_1h["Close"].resample("4h").last().dropna()
            ind = calc_indicators(hist_4h.tolist())
            if ind:
                result["4h"] = ind
    except Exception as e:
        print(f"    [{symbol} 4h] Error: {e}")

    try:
        hist_1h = await loop.run_in_executor(None, lambda: yf.Ticker(symbol).history(period="7d", interval="1h"))
        if not hist_1h.empty:
            ind = calc_indicators(hist_1h["Close"].tolist())
            if ind:
                result["1h"] = ind
    except Exception as e:
        print(f"    [{symbol} 1h] Error: {e}")

    return result if "price" in result else None

async def get_asset_data(name, info):
    try:
        if info["type"] == "crypto":
            return await get_crypto_mtf(info["symbol"])
        else:
            return await get_stock_mtf(info["symbol"])
    except Exception as e:
        print(f"  Error {name}: {e}")
        return None