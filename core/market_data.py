# core/market_data.py
import ccxt
import yfinance as yf
from datetime import datetime
from .indicators import calc_indicators

def is_market_open(asset_type):
    """
    Cek apakah pasar sedang buka.
    Crypto: 24/7
    Saham: Senin-Jumat (weekend tutup)
    """
    now = datetime.utcnow()
    if asset_type == "crypto":
        return True
    # Saham tutup Sabtu (5) dan Minggu (6)
    if now.weekday() >= 5:
        return False
    return True

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
    result = {}
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

    try:
        hist_1h = yf.Ticker(symbol).history(period="60d", interval="1h")
        if not hist_1h.empty:
            hist_4h = hist_1h["Close"].resample("4h").last().dropna()
            ind = calc_indicators(hist_4h.tolist())
            if ind:
                result["4h"] = ind
    except Exception as e:
        print(f"    [{symbol} 4h] Error: {e}")

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