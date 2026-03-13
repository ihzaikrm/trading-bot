"""
backtest/walk_forward.py
Walk-Forward Optimization (WFO) â€” quarterly parameter re-optimization.

Cara kerja:
  1. Ambil data historis (via yfinance)
  2. Rolling window: train=2 tahun, test=3 bulan, step=3 bulan
  3. Grid search params di training window â†’ ambil params terbaik
  4. Validasi di test window â†’ catat out-of-sample CAGR
  5. Simpan params optimal ke logs/optimal_params.json
  6. Bot baca params dari sana setiap run

Dipanggil oleh: core/strategy_manager.py (quarterly report)
Manual run:    python -m backtest.walk_forward --asset BTC/USDT
"""

import json
import os
import logging
import itertools
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

OPTIMAL_PARAMS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "logs", "optimal_params.json"
)

TRAIN_YEARS  = 2      # panjang window training
TEST_MONTHS  = 3      # panjang window test (1 kuartal)
STEP_MONTHS  = 3      # geser per kuartal
MIN_TRADES   = 5      # minimum trade di test window agar valid


# â”€â”€ Parameter grid per aset â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

PARAM_GRID = {
    "BTC/USDT": {
        "score_threshold": [4, 5, 6],
        "vol_ratio_min":   [1.0, 1.2, 1.5],
        "ret30d_weight":   [1, 2],
        "ret7d_weight":    [1, 2],
    },
    "GC=F": {
        "bear_ret3m":  [-0.06, -0.08, -0.10],
        "bear_ret1m":  [-0.02, -0.03, -0.05],
        "ema_span":    [150, 200],
    },
    "^GSPC": {
        "score_threshold": [4, 5, 6],
        "skip_months":     [[9], [6, 9]],
    },
}

# Default fallback jika WFO belum pernah jalan
DEFAULT_PARAMS = {
    "BTC/USDT": {"score_threshold": 5, "vol_ratio_min": 1.2, "ret30d_weight": 2, "ret7d_weight": 1},
    "GC=F":     {"bear_ret3m": -0.08, "bear_ret1m": -0.03, "ema_span": 200},
    "^GSPC":    {"score_threshold": 5, "skip_months": [9]},
}


# â”€â”€ Data fetching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _fetch_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Download OHLCV harian dari yfinance."""
    try:
        import yfinance as yf
        ticker_map = {"BTC/USDT": "BTC-USD", "GC=F": "GC=F", "^GSPC": "^GSPC"}
        ticker = ticker_map.get(symbol, symbol)
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        return df
    except Exception as e:
        logger.warning("yfinance fetch error for %s: %s", symbol, e)
        return pd.DataFrame()


# â”€â”€ Signal functions (mirror dari signal_engine.py, bisa terima params) â”€â”€â”€â”€â”€â”€â”€

def _sig_btc(closes, volumes, params):
    if len(closes) < 30 or len(volumes) < 20:
        return "HOLD"
    ret_30d   = (closes[-1] - closes[-30]) / closes[-30]
    ret_7d    = (closes[-1] - closes[-7])  / closes[-7]
    vol_ratio = volumes[-1] / (np.median(volumes[-20:]) + 1e-9)

    score = 0
    if ret_30d > 0: score += params["ret30d_weight"]
    elif ret_30d < 0: score -= params["ret30d_weight"]
    if ret_7d > 0:  score += params["ret7d_weight"]
    elif ret_7d < 0: score -= params["ret7d_weight"]

    s = pd.Series(closes)
    ema10 = float(s.ewm(span=10).mean().iloc[-1])
    ema30 = float(s.ewm(span=30).mean().iloc[-1])
    if ema10 > ema30: score += 2
    else: score -= 2

    if vol_ratio > params["vol_ratio_min"]: score += 2

    return "BUY" if score >= params["score_threshold"] else "HOLD"


def _sig_gold(closes, date, params):
    if len(closes) < params["ema_span"] + 10:
        return "HOLD"
    s = pd.Series(closes)
    ema = float(s.ewm(span=params["ema_span"]).mean().iloc[-1])
    price  = closes[-1]
    ret_3m = (closes[-1] - closes[-63]) / closes[-63] if len(closes) >= 63 else 0
    ret_1m = (closes[-1] - closes[-21]) / closes[-21] if len(closes) >= 21 else 0
    if ret_3m < params["bear_ret3m"] and ret_1m < params["bear_ret1m"]:
        return "HOLD"
    return "BUY" if price > ema else "HOLD"


def _sig_spx(closes, date, params):
    if len(closes) < 50:
        return "HOLD"
    ts = pd.Timestamp(date)
    if ts.month in params["skip_months"]:
        return "HOLD"
    s = pd.Series(closes)
    ema10 = float(s.ewm(span=10).mean().iloc[-1])
    ema30 = float(s.ewm(span=30).mean().iloc[-1])
    score = 0
    if ema10 > ema30: score += 2
    if closes[-1] > max(closes[-21:-1]): score += 2
    return "BUY" if score >= params["score_threshold"] else "HOLD"


SIGNAL_FN = {
    "BTC/USDT": _sig_btc,
    "GC=F":     _sig_gold,
    "^GSPC":    _sig_spx,
}


# â”€â”€ Backtest single window â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _backtest_window(df: pd.DataFrame, symbol: str, params: dict,
                     sl_pct=0.06, tp_pct=0.30, leverage=3.0) -> dict:
    """
    Simple daily backtest untuk satu window.
    Return: {"cagr": float, "trades": int, "winrate": float, "max_dd": float}
    """
    closes  = list(df["Close"].astype(float))
    volumes = list(df.get("Volume", pd.Series([1e6]*len(closes))).astype(float))
    dates   = list(df.index)

    in_pos     = False
    entry      = 0.0
    equity     = 1.0
    peak       = 1.0
    max_dd     = 0.0
    trades     = []
    signal_fn  = SIGNAL_FN.get(symbol)
    if signal_fn is None:
        return {"cagr": 0, "trades": 0, "winrate": 0, "max_dd": 0}

    for i in range(50, len(closes)):
        c_slice = closes[:i+1]
        v_slice = volumes[:i+1]
        date    = dates[i]
        price   = closes[i]

        if symbol == "BTC/USDT":
            sig = signal_fn(c_slice, v_slice, params)
        else:
            sig = signal_fn(c_slice, date, params)

        if in_pos:
            pnl_pct = (price - entry) / entry * leverage
            if pnl_pct <= -sl_pct or pnl_pct >= tp_pct:
                equity *= (1 + pnl_pct)
                trades.append(1 if pnl_pct > 0 else 0)
                in_pos = False
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak)
        else:
            if sig == "BUY":
                entry  = price
                in_pos = True

    if not trades:
        return {"cagr": 0.0, "trades": 0, "winrate": 0.0, "max_dd": 0.0}

    n_years = max(len(df) / 252, 1/12)
    cagr    = (equity ** (1 / n_years)) - 1
    wr      = sum(trades) / len(trades)
    return {"cagr": round(cagr, 4), "trades": len(trades), "winrate": round(wr, 4), "max_dd": round(max_dd, 4)}


# â”€â”€ Grid search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _grid_search(df_train: pd.DataFrame, symbol: str) -> dict:
    """Cari params terbaik di training window. Return best_params dict."""
    grid = PARAM_GRID.get(symbol, {})
    if not grid:
        return DEFAULT_PARAMS.get(symbol, {})

    keys   = list(grid.keys())
    values = list(grid.values())
    best_cagr   = -999
    best_params = DEFAULT_PARAMS.get(symbol, {})

    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        result = _backtest_window(df_train, symbol, params)
        if result["trades"] >= MIN_TRADES and result["cagr"] > best_cagr:
            best_cagr   = result["cagr"]
            best_params = params

    logger.info("[WFO] %s best train CAGR: %.1f%% | params: %s", symbol, best_cagr*100, best_params)
    return best_params


# â”€â”€ Walk-forward engine â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_walk_forward(symbol: str) -> dict:
    """
    Jalankan WFO untuk satu aset.
    Return summary dict dengan params optimal dan out-of-sample stats.
    """
    logger.info("[WFO] Mulai walk-forward optimization: %s", symbol)

    # Ambil data 5 tahun terakhir
    end_date   = datetime.now(timezone.utc)
    start_date = end_date - relativedelta(years=5)
    df = _fetch_data(symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    if df.empty or len(df) < 100:
        logger.warning("[WFO] Data tidak cukup untuk %s", symbol)
        return {"symbol": symbol, "status": "no_data", "params": DEFAULT_PARAMS.get(symbol, {})}

    # Rolling windows
    oos_results = []
    cursor = start_date + relativedelta(years=TRAIN_YEARS)

    while cursor + relativedelta(months=TEST_MONTHS) <= end_date:
        train_start = cursor - relativedelta(years=TRAIN_YEARS)
        train_end   = cursor
        test_end    = cursor + relativedelta(months=TEST_MONTHS)

        df_train = df[(df.index >= pd.Timestamp(train_start)) & (df.index < pd.Timestamp(train_end))]
        df_test  = df[(df.index >= pd.Timestamp(train_end))   & (df.index < pd.Timestamp(test_end))]

        if len(df_train) < 100 or len(df_test) < 10:
            cursor += relativedelta(months=STEP_MONTHS)
            continue

        best_params = _grid_search(df_train, symbol)
        oos_result  = _backtest_window(df_test, symbol, best_params)
        oos_results.append({
            "period":  f"{train_end.strftime('%Y-Q')}{(train_end.month-1)//3+1}",
            "params":  best_params,
            "oos":     oos_result,
        })
        logger.info("[WFO] %s OOS %s: CAGR=%.1f%% trades=%d",
                    symbol, oos_results[-1]["period"],
                    oos_result["cagr"]*100, oos_result["trades"])

        cursor += relativedelta(months=STEP_MONTHS)

    if not oos_results:
        return {"symbol": symbol, "status": "no_windows", "params": DEFAULT_PARAMS.get(symbol, {})}

    # Ambil params dari window terakhir (paling relevan untuk kondisi sekarang)
    latest         = oos_results[-1]
    optimal_params = latest["params"]
    avg_oos_cagr   = np.mean([r["oos"]["cagr"] for r in oos_results])
    avg_oos_wr     = np.mean([r["oos"]["winrate"] for r in oos_results if r["oos"]["trades"] >= MIN_TRADES])

    result = {
        "symbol":        symbol,
        "status":        "ok",
        "params":        optimal_params,
        "avg_oos_cagr":  round(float(avg_oos_cagr), 4),
        "avg_oos_wr":    round(float(avg_oos_wr), 4) if not np.isnan(avg_oos_wr) else 0.0,
        "n_windows":     len(oos_results),
        "updated_at":    datetime.now(timezone.utc).isoformat(),
        "windows":       oos_results,
    }
    logger.info("[WFO] %s selesai | avg OOS CAGR: %.1f%% | params: %s",
                symbol, avg_oos_cagr*100, optimal_params)
    return result


# â”€â”€ Save / Load optimal params â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def save_optimal_params(results: list[dict]) -> None:
    """Simpan semua hasil WFO ke logs/optimal_params.json."""
    os.makedirs(os.path.dirname(OPTIMAL_PARAMS_FILE), exist_ok=True)
    existing = load_optimal_params_raw()
    for r in results:
        if r.get("status") == "ok":
            existing[r["symbol"]] = r
    existing["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(OPTIMAL_PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, default=str)
    logger.info("[WFO] Params disimpan ke %s", OPTIMAL_PARAMS_FILE)


def load_optimal_params_raw() -> dict:
    """Load raw file optimal_params.json."""
    try:
        with open(OPTIMAL_PARAMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_optimal_params(symbol: str) -> dict:
    """
    Public API â€” dipanggil dari config/assets.py atau signal_engine.py.
    Return params optimal untuk aset, fallback ke default jika belum ada.
    """
    raw = load_optimal_params_raw()
    entry = raw.get(symbol, {})
    if entry.get("status") == "ok" and entry.get("params"):
        return entry["params"]
    return DEFAULT_PARAMS.get(symbol, {})


def wfo_summary() -> str:
    """String ringkasan untuk Telegram quarterly report."""
    raw = load_optimal_params_raw()
    last_run = raw.get("last_run", "belum pernah")[:19].replace("T", " ")
    lines = [f"ðŸ”„ *Walk-Forward Optimization*", f"Last run: {last_run} UTC", ""]

    for symbol in ["BTC/USDT", "GC=F", "^GSPC"]:
        entry = raw.get(symbol, {})
        if entry.get("status") == "ok":
            cagr = entry.get("avg_oos_cagr", 0) * 100
            wr   = entry.get("avg_oos_wr", 0) * 100
            n    = entry.get("n_windows", 0)
            p    = entry.get("params", {})
            lines.append(f"*{symbol}*")
            lines.append(f"  OOS CAGR: {cagr:.1f}% | WR: {wr:.1f}% | {n} windows")
            lines.append(f"  Params: {p}")
        else:
            lines.append(f"*{symbol}*: belum dioptimasi")
        lines.append("")

    return "\n".join(lines)


# â”€â”€ Run semua aset (dipanggil quarterly) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_quarterly_wfo() -> str:
    """
    Entry point dari strategy_manager.py.
    Optimasi semua aset, simpan hasil, return summary string.
    """
    logger.info("[WFO] Mulai quarterly WFO untuk semua aset")
    assets  = ["BTC/USDT", "GC=F", "^GSPC"]
    results = []
    for symbol in assets:
        try:
            r = run_walk_forward(symbol)
            results.append(r)
        except Exception as e:
            logger.error("[WFO] Error %s: %s", symbol, e)
            results.append({"symbol": symbol, "status": "error", "params": DEFAULT_PARAMS.get(symbol, {})})
    save_optimal_params(results)
    return wfo_summary()


# â”€â”€ CLI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if "--all" in sys.argv:
        print(run_quarterly_wfo())
    elif "--summary" in sys.argv:
        print(wfo_summary())
    else:
        # Default: satu aset dari arg
        symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
        r = run_walk_forward(symbol)
        print(json.dumps(r, indent=2, default=str))
