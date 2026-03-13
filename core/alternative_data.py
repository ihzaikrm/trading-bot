"""
core/alternative_data.py
H5: Alternative data untuk sinyal tambahan.

Sumber (semua FREE, no API key):
  BTC on-chain:
    - Fear & Greed Index (alternative.me) â€” sudah ada, diperkaya
    - Hashrate via blockchain.info (public)
    - Exchange netflow proxy via CoinGecko volume ratio
    - Long/Short ratio via Binance public API

  SPX options flow:
    - Put/Call ratio via CBOE (public CSV)
    - VIX level via Yahoo Finance
    - AAII sentiment proxy via fear/greed

Cara pakai di signal_engine.py:
    from core.alternative_data import get_btc_onchain, get_spx_options_flow
    btc_alt  = get_btc_onchain()
    spx_flow = get_spx_options_flow()
"""

import json
import os
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "alt_data_cache.json")
CACHE_TTL  = 3600  # 1 jam dalam detik


# â”€â”€ Cache helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _load_cache() -> dict:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(data: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _is_fresh(cache: dict, key: str, ttl: int = CACHE_TTL) -> bool:
    entry = cache.get(key, {})
    ts    = entry.get("timestamp", 0)
    return (time.time() - ts) < ttl


def _fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "TradingBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning("Fetch error %s: %s", url, e)
        return None


def _fetch_text(url: str, timeout: int = 10) -> Optional[str]:
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "TradingBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning("Fetch text error %s: %s", url, e)
        return None


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BTC On-Chain Data
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _get_fear_greed() -> dict:
    """Fear & Greed Index dari alternative.me (0=extreme fear, 100=extreme greed)."""
    data = _fetch_json("https://api.alternative.me/fng/?limit=2")
    if not data:
        return {"value": 50, "label": "Neutral", "signal": "NEUTRAL"}
    try:
        current = int(data["data"][0]["value"])
        label   = data["data"][0]["value_classification"]
        prev    = int(data["data"][1]["value"]) if len(data["data"]) > 1 else current
        delta   = current - prev

        if current <= 20:
            signal = "STRONG_BUY"    # extreme fear = buy
        elif current <= 35:
            signal = "BUY"
        elif current >= 80:
            signal = "STRONG_SELL"   # extreme greed = sell
        elif current >= 65:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        return {"value": current, "label": label, "delta": delta, "signal": signal}
    except (KeyError, IndexError, ValueError):
        return {"value": 50, "label": "Neutral", "signal": "NEUTRAL"}


def _get_binance_long_short() -> dict:
    """
    Long/Short ratio dari Binance public API (BTCUSDT perp).
    Ratio > 1 = lebih banyak long = bearish contrarian signal.
    """
    url  = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=2"
    data = _fetch_json(url)
    if not data or not isinstance(data, list) or len(data) == 0:
        return {"ratio": 1.0, "long_pct": 50.0, "signal": "NEUTRAL"}
    try:
        latest    = data[-1]
        ratio     = float(latest["longShortRatio"])
        long_pct  = float(latest["longAccount"]) * 100
        # Contrarian: terlalu banyak long â†’ crowded â†’ potential reversal
        if ratio >= 1.8:
            signal = "BEARISH"   # terlalu crowded long
        elif ratio <= 0.7:
            signal = "BULLISH"   # terlalu crowded short = short squeeze potential
        else:
            signal = "NEUTRAL"
        return {"ratio": round(ratio, 3), "long_pct": round(long_pct, 1), "signal": signal}
    except (KeyError, ValueError, IndexError):
        return {"ratio": 1.0, "long_pct": 50.0, "signal": "NEUTRAL"}


def _get_btc_volume_ratio() -> dict:
    """
    Proxy exchange netflow dari CoinGecko volume ratio.
    Volume spike + price drop â†’ kemungkinan outflow ke exchange (bearish).
    Volume spike + price up   â†’ inflow dari exchange (bullish).
    """
    url  = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7&interval=daily"
    data = _fetch_json(url)
    if not data:
        return {"vol_ratio": 1.0, "signal": "NEUTRAL"}
    try:
        volumes = [v[1] for v in data.get("total_volumes", [])]
        prices  = [p[1] for p in data.get("prices", [])]
        if len(volumes) < 3 or len(prices) < 3:
            return {"vol_ratio": 1.0, "signal": "NEUTRAL"}

        avg_vol   = sum(volumes[:-1]) / len(volumes[:-1])
        last_vol  = volumes[-1]
        vol_ratio = last_vol / (avg_vol + 1e-9)
        ret_7d    = (prices[-1] - prices[0]) / prices[0]

        if vol_ratio > 1.5 and ret_7d > 0.05:
            signal = "BULLISH"    # volume tinggi + naik
        elif vol_ratio > 1.5 and ret_7d < -0.05:
            signal = "BEARISH"    # volume tinggi + turun
        else:
            signal = "NEUTRAL"

        return {"vol_ratio": round(vol_ratio, 3), "ret_7d": round(ret_7d, 4), "signal": signal}
    except (KeyError, ValueError, ZeroDivisionError):
        return {"vol_ratio": 1.0, "signal": "NEUTRAL"}


def get_btc_onchain(use_cache: bool = True) -> dict:
    """
    Agregasi semua BTC alternative data.
    Return dict dengan composite signal dan breakdown.

    Contoh output:
    {
        "composite_signal": "BULLISH",   # STRONG_BULLISH/BULLISH/NEUTRAL/BEARISH/STRONG_BEARISH
        "composite_score": 2,            # -4 s/d +4
        "fear_greed": {"value":25, "signal":"BUY"},
        "long_short":  {"ratio":0.8, "signal":"BULLISH"},
        "vol_flow":    {"vol_ratio":1.3, "signal":"NEUTRAL"},
        "summary":     "FG:25(BUY) | L/S:0.80(BULL) | Vol:1.30(NEUTRAL)"
    }
    """
    cache = _load_cache() if use_cache else {}
    cache_key = "btc_onchain"

    if use_cache and _is_fresh(cache, cache_key):
        return cache[cache_key]["data"]

    fg       = _get_fear_greed()
    ls       = _get_binance_long_short()
    vol_flow = _get_btc_volume_ratio()

    # Score: +2=strong bullish, +1=bullish, 0=neutral, -1=bearish, -2=strong bearish
    score_map = {
        "STRONG_BUY": 2, "BUY": 1, "NEUTRAL": 0, "SELL": -1, "STRONG_SELL": -2,
        "STRONG_BULLISH": 2, "BULLISH": 1, "BEARISH": -1, "STRONG_BEARISH": -2,
    }
    score = (
        score_map.get(fg["signal"], 0) +
        score_map.get(ls["signal"], 0) +
        score_map.get(vol_flow["signal"], 0)
    )

    if score >= 3:      composite = "STRONG_BULLISH"
    elif score >= 1:    composite = "BULLISH"
    elif score <= -3:   composite = "STRONG_BEARISH"
    elif score <= -1:   composite = "BEARISH"
    else:               composite = "NEUTRAL"

    result = {
        "composite_signal": composite,
        "composite_score":  score,
        "fear_greed":       fg,
        "long_short":       ls,
        "vol_flow":         vol_flow,
        "summary": (
            f"FG:{fg['value']}({fg['signal']}) | "
            f"L/S:{ls['ratio']}({ls['signal']}) | "
            f"Vol:{vol_flow['vol_ratio']}({vol_flow['signal']})"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    cache[cache_key] = {"data": result, "timestamp": time.time()}
    _save_cache(cache)
    return result


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SPX Options Flow
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _get_vix() -> dict:
    """VIX dari Yahoo Finance (proxy fear untuk SPX)."""
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if hist.empty:
            return {"value": 20.0, "signal": "NEUTRAL"}
        value = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2]) if len(hist) > 1 else value
        delta = value - prev

        if value >= 30:
            signal = "BULLISH"      # high VIX = fear = contrarian buy
        elif value >= 25:
            signal = "MILD_BULL"
        elif value <= 12:
            signal = "BEARISH"      # low VIX = complacency = potential top
        elif value <= 15:
            signal = "MILD_BEAR"
        else:
            signal = "NEUTRAL"

        return {"value": round(value, 2), "delta": round(delta, 2), "signal": signal}
    except Exception as e:
        logger.warning("VIX fetch error: %s", e)
        return {"value": 20.0, "signal": "NEUTRAL"}


def _get_put_call_ratio() -> dict:
    """
    Put/Call ratio dari CBOE public data.
    PCR > 1.0 = bearish sentiment (banyak put) = contrarian bullish.
    PCR < 0.7 = bullish sentiment (banyak call) = contrarian bearish.
    """
    url  = "https://www.cboe.com/publish/scheduledtask/mktdata/datahouse/equitypc.csv"
    text = _fetch_text(url)
    if not text:
        return {"pcr": 0.85, "signal": "NEUTRAL"}
    try:
        lines = [l for l in text.strip().split("\n") if l and not l.startswith("DATE")]
        if not lines:
            return {"pcr": 0.85, "signal": "NEUTRAL"}
        last  = lines[-1].split(",")
        # Format: DATE, CALL, PUT, TOTAL, P/C RATIO
        pcr   = float(last[-1].strip()) if last[-1].strip() else 0.85

        if pcr >= 1.0:
            signal = "BULLISH"       # contrarian: fear = buy
        elif pcr >= 0.85:
            signal = "MILD_BULL"
        elif pcr <= 0.6:
            signal = "BEARISH"       # contrarian: greed = sell
        elif pcr <= 0.7:
            signal = "MILD_BEAR"
        else:
            signal = "NEUTRAL"

        return {"pcr": round(pcr, 3), "signal": signal}
    except (ValueError, IndexError):
        return {"pcr": 0.85, "signal": "NEUTRAL"}


def get_spx_options_flow(use_cache: bool = True) -> dict:
    """
    Agregasi SPX options flow + VIX.
    Return dict dengan composite signal.

    Contoh output:
    {
        "composite_signal": "BULLISH",
        "composite_score": 1,
        "vix":  {"value": 22.5, "signal": "MILD_BULL"},
        "pcr":  {"pcr": 0.92, "signal": "BULLISH"},
        "summary": "VIX:22.5(MILD_BULL) | PCR:0.92(BULL)"
    }
    """
    cache = _load_cache() if use_cache else {}
    cache_key = "spx_options"

    if use_cache and _is_fresh(cache, cache_key, ttl=7200):  # 2 jam
        return cache[cache_key]["data"]

    vix = _get_vix()
    pcr = _get_put_call_ratio()

    score_map = {
        "BULLISH": 2, "MILD_BULL": 1, "NEUTRAL": 0, "MILD_BEAR": -1, "BEARISH": -2
    }
    score = score_map.get(vix["signal"], 0) + score_map.get(pcr["signal"], 0)

    if score >= 3:      composite = "STRONG_BULLISH"
    elif score >= 1:    composite = "BULLISH"
    elif score <= -3:   composite = "STRONG_BEARISH"
    elif score <= -1:   composite = "BEARISH"
    else:               composite = "NEUTRAL"

    result = {
        "composite_signal": composite,
        "composite_score":  score,
        "vix":              vix,
        "pcr":              pcr,
        "summary":          f"VIX:{vix['value']}({vix['signal']}) | PCR:{pcr['pcr']}({pcr['signal']})",
        "timestamp":        datetime.now(timezone.utc).isoformat(),
    }

    cache[cache_key] = {"data": result, "timestamp": time.time()}
    _save_cache(cache)
    return result


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Wire ke signal_engine.py â€” tambah ke prompt LLM
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def get_alt_data_for_prompt(asset_name: str) -> str:
    """
    Return string siap pakai untuk dimasukkan ke LLM prompt.
    Dipanggil dari signal_engine.py di fungsi get_signal().
    """
    lines = []
    try:
        if "BTC" in asset_name:
            btc = get_btc_onchain()
            lines.append(f"On-chain: {btc['summary']} â†’ {btc['composite_signal']}")
        elif "GSPC" in asset_name or "SPX" in asset_name:
            spx = get_spx_options_flow()
            lines.append(f"Options flow: {spx['summary']} â†’ {spx['composite_signal']}")
    except Exception as e:
        logger.warning("Alt data error for %s: %s", asset_name, e)
    return "\n".join(lines)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CLI
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if "--btc" in sys.argv:
        r = get_btc_onchain(use_cache=False)
        print(json.dumps(r, indent=2))
    elif "--spx" in sys.argv:
        r = get_spx_options_flow(use_cache=False)
        print(json.dumps(r, indent=2))
    else:
        print("Usage: python -m core.alternative_data [--btc | --spx]")
