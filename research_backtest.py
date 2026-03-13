# research_backtest.py
# Backtest semua strategi berbasis SSRN research papers
# BTC: Short-term momentum, Volume-weighted momentum, Abnormal return filter
# Gold: Seasonal (Jul-Feb), Day-of-week (no Monday), Adaptive
# SPX: Sell-in-May, Monthly seasonality, Turn-of-month, Demand imbalance momentum

import sys, os
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np
from datetime import datetime
from backtest.data_loader import load_data
from core.indicators import calc_indicators

INITIAL  = 1000.0
LEVERAGE = 3
YEARS    = 10
START    = "2015-01-01"
END      = "2024-12-31"
RF_RATE  = 0.05

# ─── Metrics ─────────────────────────────────────────────────────────────────

def cagr(final, years=YEARS):
    if final <= 0: return -99.9
    return round(((final/INITIAL)**(1/years)-1)*100, 1)

def sharpe(equity, years=YEARS):
    eq = np.array(equity)
    if len(eq) < 2: return 0.0
    dr = np.diff(eq)/eq[:-1]
    if dr.std() == 0: return 0.0
    ar = (eq[-1]/eq[0])**(1/years)-1
    return round((ar-RF_RATE)/(dr.std()*np.sqrt(252)), 2)

def max_dd(equity):
    eq = np.array(equity)
    pk = np.maximum.accumulate(eq)
    return round(float(((eq-pk)/pk*100).min()), 1)

def calmar(c, dd):
    return round(c/abs(dd), 3) if dd != 0 else 0.0

def sortino(equity, years=YEARS):
    eq = np.array(equity)
    if len(eq) < 2: return 0.0
    dr = np.diff(eq)/eq[:-1]
    dv = dr[dr<0].std()
    if dv == 0: return 0.0
    ar = (eq[-1]/eq[0])**(1/years)-1
    return round((ar-RF_RATE)/(dv*np.sqrt(252)), 2)

def winrate(trades):
    if not trades: return 0.0
    return round(sum(1 for t in trades if t>0)/len(trades)*100, 1)

def metrics(equity, pnls, years=YEARS):
    c  = cagr(equity[-1], years)
    dd = max_dd(equity)
    return {
        "cagr":    c,
        "final":   round(equity[-1], 2),
        "dd":      dd,
        "sharpe":  sharpe(equity, years),
        "sortino": sortino(equity, years),
        "calmar":  calmar(c, dd),
        "wr":      winrate(pnls),
        "trades":  len(pnls),
    }

def bh(df, lev=LEVERAGE, years=YEARS):
    s  = df["close"].iloc[0]
    eq = [max(INITIAL*(1+(p-s)/s*lev), 0.01) for p in df["close"]]
    c  = cagr(eq[-1], years)
    return {"cagr":c, "dd":max_dd(eq), "sharpe":sharpe(eq,years)}

def prow(label, r, bh_cagr, w=38):
    beat = "✅" if r["cagr"] > bh_cagr else "❌"
    sg   = "🟢" if r["sharpe"]>1.5 else ("🟡" if r["sharpe"]>0.8 else "🔴")
    print(f"  {label:<{w}} | CAGR:{r['cagr']:6.1f}%{beat}"
          f" | DD:{r['dd']:6.1f}%"
          f" | Sharpe:{r['sharpe']:5.2f}{sg}"
          f" | Sortino:{r['sortino']:5.2f}"
          f" | Calmar:{r['calmar']:5.3f}"
          f" | WR:{r['wr']:5.1f}% | T:{r['trades']}")

# ─── Core Backtest Engine ─────────────────────────────────────────────────────

def backtest(df, sl, tp, lev, signal_fn, years=YEARS, **kw):
    closes  = df["close"].tolist()
    dates   = list(df.index)
    volumes = df["volume"].tolist() if "volume" in df.columns else [1]*len(closes)
    balance = INITIAL
    pos     = None
    pnls    = []
    equity  = [INITIAL]

    for i in range(252, len(closes)):
        price = closes[i]
        date  = dates[i]
        ind   = calc_indicators(closes[:i+1])
        if ind is None: continue

        sig = signal_fn(ind, closes[:i+1], date, volumes[:i+1], **kw)

        if pos:
            pnl_pct = ((price-pos["e"])/pos["e"]*100*lev if pos["t"]=="long"
                       else (pos["e"]-price)/pos["e"]*100*lev)
            if pnl_pct <= -sl or pnl_pct >= tp:
                pnl = ((price-pos["e"])*pos["q"] if pos["t"]=="long"
                       else (pos["e"]-price)*pos["q"])
                balance += pos["a"] + pnl
                pnls.append(pnl)
                pos = None
                equity.append(balance)
                continue

        if not pos:
            if sig == "BUY":
                pos = {"t":"long",  "e":price, "q":(balance*lev)/price, "a":balance}
                balance = 0
            elif sig == "SELL":
                pos = {"t":"short", "e":price, "q":(balance*lev)/price, "a":balance}
                balance = 0

    if pos:
        price = closes[-1]
        pnl   = ((price-pos["e"])*pos["q"] if pos["t"]=="long"
                 else (pos["e"]-price)*pos["q"])
        balance += pos["a"] + pnl
        pnls.append(pnl)
        equity.append(balance)

    return metrics(equity, pnls, years)

# ═══════════════════════════════════════════════════════════════════════════
# BTC STRATEGIES (dari SSRN research)
# ═══════════════════════════════════════════════════════════════════════════

def btc_baseline(ind, closes, date, vols, **kw):
    """Baseline: momentum standar"""
    score = 0
    if ind["ema_trend"] == "BULLISH": score += 3
    elif ind["ema_trend"] == "BEARISH": score -= 3
    if ind["macd_cross"] == "BULLISH": score += 2
    else: score -= 2
    if ind["rsi"] < 30: score += 1
    elif ind["rsi"] > 70: score -= 1
    if score >= 3: return "BUY"
    return "HOLD"

def btc_short_momentum(ind, closes, date, vols, lookback_short=7, lookback_long=30, **kw):
    """
    Paper: Cross-Sectional Momentum (2023)
    Aset yang perform 30 hari terbaik → terus outperform 7 hari ke depan.
    Ganti lookback dari 12 bulan → 30 hari sebagai sinyal utama.
    """
    if len(closes) < lookback_long + 1: return "HOLD"
    ret_30d = (closes[-1] - closes[-lookback_long]) / closes[-lookback_long]
    ret_7d  = (closes[-1] - closes[-lookback_short]) / closes[-lookback_short]

    # Entry: 30d dan 7d sama-sama positif + EMA bullish
    if ret_30d > 0.05 and ret_7d > 0.01 and ind["ema_trend"] == "BULLISH":
        return "BUY"
    # Exit: momentum berbalik
    if ret_30d < -0.05 or ret_7d < -0.03:
        return "SELL"
    return "HOLD"

def btc_volume_weighted_momentum(ind, closes, date, vols, **kw):
    """
    Paper: Volume-Weighted Time Series Momentum (Huang et al. 2024)
    TSMOM dengan volume weighting — signal lebih kuat kalau volume tinggi.
    """
    if len(closes) < 30 or len(vols) < 20: return "HOLD"
    ret_30d = (closes[-1] - closes[-30]) / closes[-30]
    ret_7d  = (closes[-1] - closes[-7])  / closes[-7]

    # Volume weight: rasio volume hari ini vs median 20 hari
    vol_ratio = vols[-1] / (np.median(vols[-20:]) + 1e-9)
    vol_strong = vol_ratio > 1.2  # volume 20% di atas median

    score = 0
    if ret_30d > 0: score += 2
    if ret_7d  > 0: score += 1
    if ind["ema_trend"] == "BULLISH": score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if vol_strong: score += 2  # bonus dari volume weighting

    if score >= 5: return "BUY"
    if score <= -3: return "SELL"
    return "HOLD"

def btc_abnormal_return(ind, closes, date, vols, threshold=0.04, **kw):
    """
    Paper: Intraday Momentum setelah Abnormal Returns
    Kalau BTC sudah naik >4% dalam sehari → pertahankan/tambah posisi.
    Kalau sudah turun >4% → pertahankan short / hindari long.
    """
    if len(closes) < 30: return "HOLD"
    daily_ret = (closes[-1] - closes[-2]) / closes[-2] if len(closes) >= 2 else 0
    ret_30d   = (closes[-1] - closes[-30]) / closes[-30]

    # Abnormal positive return + momentum bullish → BUY signal kuat
    if daily_ret > threshold and ret_30d > 0 and ind["ema_trend"] == "BULLISH":
        return "BUY"
    # Abnormal negative return + bearish → hindari entry
    if daily_ret < -threshold and ret_30d < 0:
        return "SELL"

    # Fallback ke momentum standar
    score = 0
    if ind["ema_trend"] == "BULLISH": score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if ind["rsi"] < 35: score += 1
    if score >= 3: return "BUY"
    return "HOLD"

def btc_combined_research(ind, closes, date, vols, **kw):
    """
    KOMBINASI semua 3 paper BTC:
    Short momentum (30d/7d) + Volume weighted + Abnormal return filter
    """
    if len(closes) < 252 or len(vols) < 20: return "HOLD"

    ret_30d = (closes[-1] - closes[-30]) / closes[-30]
    ret_7d  = (closes[-1] - closes[-7])  / closes[-7]
    ret_1d  = (closes[-1] - closes[-2])  / closes[-2] if len(closes) >= 2 else 0

    vol_ratio  = vols[-1] / (np.median(vols[-20:]) + 1e-9)
    vol_strong = vol_ratio > 1.1

    score = 0
    # Short-term momentum
    if ret_30d > 0.03: score += 2
    elif ret_30d < -0.03: score -= 2
    if ret_7d > 0.01: score += 1
    elif ret_7d < -0.01: score -= 1

    # Volume weighting
    if vol_strong and ret_1d > 0: score += 1
    if vol_strong and ret_1d < 0: score -= 1

    # Abnormal return momentum
    if ret_1d > 0.03: score += 1
    elif ret_1d < -0.03: score -= 1

    # Technical confirmation
    if ind["ema_trend"] == "BULLISH": score += 2
    elif ind["ema_trend"] == "BEARISH": score -= 2
    if ind["macd_cross"] == "BULLISH": score += 1
    else: score -= 1

    if score >= 5: return "BUY"
    if score <= -4: return "SELL"
    return "HOLD"

# ═══════════════════════════════════════════════════════════════════════════
# GOLD STRATEGIES (dari SSRN research)
# ═══════════════════════════════════════════════════════════════════════════

GOLD_BULL_MONTHS  = [7, 8, 9, 10, 11, 12, 1, 2]   # Juli-Februari (bull season)
GOLD_BEAR_MONTHS  = [3, 4, 5, 6]                    # Maret-Juni (bear season)
GOLD_SKIP_DAYS    = [0]  # Senin (0=Monday) — return negatif per research

def gold_baseline(ind, closes, date, vols, **kw):
    """Baseline Gold: adaptive (trending vs ranging)"""
    if len(closes) < 200: return "HOLD"
    s      = pd.Series(closes)
    ema50  = float(s.ewm(span=50).mean().iloc[-1])
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]
    ret_3m = (closes[-1]-closes[-63])/closes[-63] if len(closes)>=63 else 0
    vol_20 = float(pd.Series(closes[-20:]).pct_change().std()*np.sqrt(252))

    is_trending = abs(ret_3m) > 0.08 and vol_20 > 0.12

    if is_trending:
        if len(closes) >= 21:
            high20 = max(closes[-21:-1])
            if price > high20 and (ema50 > ema200 or ind["ema_trend"] == "BULLISH"):
                return "BUY"
        return "HOLD"
    else:
        s50   = pd.Series(closes[-50:])
        ma    = float(s50.rolling(20).mean().iloc[-1])
        std   = float(s50.rolling(20).std().iloc[-1])
        if std == 0: return "HOLD"
        z = (closes[-1] - ma) / std
        if z < -2.2 and ind["rsi"] < 40 and ind["bb_pos"] == "OVERSOLD":
            return "BUY"
        if z > 2.2 and ind["rsi"] > 60:
            return "SELL"
    return "HOLD"

def gold_seasonal(ind, closes, date, vols, **kw):
    """
    Paper: Gold Calendar Anomalies + Seasonality
    - Jangan trade hari Senin (return negatif)
    - Bull season Juli-Februari: lebih agresif buka long
    - Bear season Maret-Juni: kurangi posisi / skip long
    """
    if len(closes) < 200: return "HOLD"
    month    = date.month if hasattr(date, "month") else pd.Timestamp(date).month
    weekday  = date.weekday() if hasattr(date, "weekday") else pd.Timestamp(date).weekday()

    # Skip hari Senin
    if weekday in GOLD_SKIP_DAYS:
        return "HOLD"

    is_bull_season = month in GOLD_BULL_MONTHS
    is_bear_season = month in GOLD_BEAR_MONTHS

    # Seasonal score
    seasonal_score = 1 if is_bull_season else (-1 if is_bear_season else 0)

    # Technical signal
    s      = pd.Series(closes)
    ema50  = float(s.ewm(span=50).mean().iloc[-1])
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]
    ret_3m = (closes[-1]-closes[-63])/closes[-63] if len(closes)>=63 else 0
    vol_20 = float(pd.Series(closes[-20:]).pct_change().std()*np.sqrt(252))
    is_trending = abs(ret_3m) > 0.08 and vol_20 > 0.12

    tech_score = 0
    if ind["ema_trend"] == "BULLISH": tech_score += 2
    elif ind["ema_trend"] == "BEARISH": tech_score -= 2
    if ind["macd_cross"] == "BULLISH": tech_score += 1
    else: tech_score -= 1
    if ind["rsi"] < 35: tech_score += 1
    elif ind["rsi"] > 65: tech_score -= 1

    # Turtle dalam bull season
    if is_trending and is_bull_season and len(closes) >= 21:
        high20 = max(closes[-21:-1])
        if price > high20 and ind["ema_trend"] == "BULLISH":
            return "BUY"

    # Mean reversion dalam sideways
    if not is_trending:
        s50  = pd.Series(closes[-50:])
        ma   = float(s50.rolling(20).mean().iloc[-1])
        std  = float(s50.rolling(20).std().iloc[-1])
        if std > 0:
            z = (closes[-1] - ma) / std
            if z < -2.0 and tech_score > 0 and seasonal_score >= 0:
                return "BUY"
            if z > 2.0 and tech_score < 0:
                return "SELL"

    # Bear season: lebih konservatif
    total = tech_score + seasonal_score * 2
    if total >= 4 and is_bull_season: return "BUY"
    if total <= -3: return "SELL"
    return "HOLD"

def gold_combined_research(ind, closes, date, vols, **kw):
    """
    KOMBINASI semua research Gold:
    Seasonal filter (Jul-Feb) + Day-of-week (no Monday) +
    Market timing (keluar setelah tren negatif berkepanjangan) +
    Adaptive (trending/ranging)
    """
    if len(closes) < 200: return "HOLD"
    month   = date.month if hasattr(date, "month") else pd.Timestamp(date).month
    weekday = date.weekday() if hasattr(date, "weekday") else pd.Timestamp(date).weekday()

    # Filter 1: Skip Senin
    if weekday == 0: return "HOLD"

    # Filter 2: Seasonal bias
    bull_season = month in GOLD_BULL_MONTHS
    bear_season = month in GOLD_BEAR_MONTHS

    # Filter 3: Market timing — keluar kalau tren negatif >3 bulan berturut
    ret_3m = (closes[-1]-closes[-63])/closes[-63] if len(closes)>=63 else 0
    ret_1m = (closes[-1]-closes[-21])/closes[-21] if len(closes)>=21 else 0
    prolonged_bear = ret_3m < -0.08 and ret_1m < -0.03

    if prolonged_bear and bear_season:
        return "HOLD"  # Keluar dari market

    # Filter 4: Regime (trending vs ranging)
    s      = pd.Series(closes)
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    ema50  = float(s.ewm(span=50).mean().iloc[-1])
    price  = closes[-1]
    vol_20 = float(pd.Series(closes[-20:]).pct_change().std()*np.sqrt(252))
    is_trending = abs(ret_3m) > 0.08 and vol_20 > 0.12

    # Turtle untuk trending bull
    if is_trending and bull_season and price > ema200:
        if len(closes) >= 21:
            high20 = max(closes[-21:-1])
            if price > high20:
                return "BUY"

    # Mean reversion untuk ranging
    if not is_trending:
        s50  = pd.Series(closes[-50:])
        ma   = float(s50.rolling(20).mean().iloc[-1])
        std  = float(s50.rolling(20).std().iloc[-1])
        if std > 0:
            z = (closes[-1] - ma) / std
            rsi_ok   = ind["rsi"] < 38
            stoch_ok = ind["stoch_signal"] == "OVERSOLD"
            bb_ok    = ind["bb_pos"] == "OVERSOLD"

            if z < -2.0 and sum([rsi_ok, stoch_ok, bb_ok]) >= 2 and not bear_season:
                return "BUY"
            if z > 2.2 and ind["rsi"] > 62:
                return "SELL"

    return "HOLD"

# ═══════════════════════════════════════════════════════════════════════════
# SPX STRATEGIES (dari SSRN research)
# ═══════════════════════════════════════════════════════════════════════════

SPX_STRONG_MONTHS = [1, 4, 7, 11]    # Jan, Apr, Jul, Nov — 80% green rate
SPX_WEAK_MONTHS   = [6, 9]           # Jun, Sep — worst months
SPX_WINTER_MONTHS = [11, 12, 1, 2, 3, 4]  # Nov-Apr: "Sell in May" effect
SPX_SUMMER_MONTHS = [5, 6, 7, 8, 9, 10]   # May-Oct: avoid

def spx_baseline(ind, closes, date, vols, **kw):
    """Baseline SPX: Turtle breakout"""
    if len(closes) < 21: return "HOLD"
    high20 = max(closes[-21:-1])
    if closes[-1] > high20 and ind["ema_trend"] == "BULLISH":
        return "BUY"
    return "HOLD"

def spx_sell_in_may(ind, closes, date, vols, **kw):
    """
    Paper: Sell in May and Go Away (SSRN — 300 years data)
    Winter (Nov-Apr) return >> Summer (May-Oct).
    Strategy beats market 80%+ over 5-year horizons.
    """
    if len(closes) < 21: return "HOLD"
    month = date.month if hasattr(date, "month") else pd.Timestamp(date).month

    is_winter = month in SPX_WINTER_MONTHS
    is_summer = month in SPX_SUMMER_MONTHS

    if is_summer: return "HOLD"  # Keluar dari market Mei-Oktober

    # Di winter: gunakan trend-following biasa
    high20 = max(closes[-21:-1])
    if closes[-1] > high20 and ind["ema_trend"] == "BULLISH":
        return "BUY"
    return "HOLD"

def spx_monthly_seasonal(ind, closes, date, vols, **kw):
    """
    Research: April, July, November = 80% green rate
    June, September = worst months
    Tambahkan seasonal multiplier ke signal strength
    """
    if len(closes) < 21: return "HOLD"
    month = date.month if hasattr(date, "month") else pd.Timestamp(date).month

    # Dalam weak month: skip semua entry
    if month in SPX_WEAK_MONTHS: return "HOLD"

    # Technical signal
    score = 0
    high20 = max(closes[-21:-1])
    if closes[-1] > high20: score += 3  # Turtle breakout
    if ind["ema_trend"] == "BULLISH": score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if ind["rsi"] > 50: score += 1

    # Bonus di strong months
    if month in SPX_STRONG_MONTHS: score += 1

    if score >= 5: return "BUY"
    return "HOLD"

def spx_turn_of_month(ind, closes, date, vols, **kw):
    """
    Paper: Composite Seasonal — Turn-of-Month Effect
    Hari trading ke-1 s/d ke-3 setiap bulan secara historis lebih bullish.
    Dikombinasikan dengan trend factor.
    """
    if len(closes) < 21: return "HOLD"
    try:
        ts   = pd.Timestamp(date)
        day  = ts.day
        month = ts.month
    except:
        return "HOLD"

    # Turn-of-month: hari 28-31 bulan ini + hari 1-3 bulan depan
    is_turn_of_month = day >= 28 or day <= 3

    # Trend factor (EMA filter)
    trend_bullish = ind["ema_trend"] == "BULLISH"

    # Tidak trade di bulan lemah
    if month in SPX_WEAK_MONTHS: return "HOLD"

    score = 0
    if trend_bullish: score += 3
    if ind["macd_cross"] == "BULLISH": score += 1

    high20 = max(closes[-21:-1])
    if closes[-1] > high20: score += 2

    # Bonus di turn-of-month
    if is_turn_of_month: score += 2

    if score >= 5: return "BUY"
    return "HOLD"

def spx_demand_imbalance(ind, closes, date, vols, **kw):
    """
    Paper: Zarattini et al. 2024 — Demand/Supply Imbalance Momentum
    Proxy harian: return kemarin sebagai indikator demand imbalance.
    Jika kemarin naik signifikan → demand imbalance → continue momentum.
    """
    if len(closes) < 30: return "HOLD"
    ret_1d = (closes[-1]-closes[-2])/closes[-2] if len(closes)>=2 else 0
    ret_5d = (closes[-1]-closes[-6])/closes[-6] if len(closes)>=6 else 0
    ret_20d= (closes[-1]-closes[-21])/closes[-21] if len(closes)>=21 else 0

    # Abnormal demand signal: naik >0.5% kemarin + trend bullish
    demand_signal = ret_1d > 0.005 and ret_5d > 0
    supply_signal = ret_1d < -0.005 and ret_5d < 0

    score = 0
    if ind["ema_trend"] == "BULLISH": score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if ret_20d > 0.02: score += 1
    if demand_signal: score += 2

    if score >= 4: return "BUY"
    return "HOLD"

def spx_combined_research(ind, closes, date, vols, **kw):
    """
    KOMBINASI semua SPX research:
    Sell-in-May + Monthly seasonal + Turn-of-month + Demand imbalance + Trend
    """
    if len(closes) < 30: return "HOLD"
    try:
        ts    = pd.Timestamp(date)
        month = ts.month
        day   = ts.day
    except:
        return "HOLD"

    # Layer 1: Sell-in-May filter — keluar total di Jun & Sep
    if month in SPX_WEAK_MONTHS: return "HOLD"
    if month in SPX_SUMMER_MONTHS:
        # Di summer: hanya masuk kalau semua konfirmasi sangat kuat
        min_score = 7
    else:
        # Di winter: threshold lebih rendah
        min_score = 4

    # Layer 2: Scoring
    score = 0

    # Seasonal bonus
    if month in SPX_WINTER_MONTHS: score += 1
    if month in SPX_STRONG_MONTHS: score += 1

    # Turn of month bonus
    if day >= 28 or day <= 3: score += 1

    # Demand imbalance
    ret_1d = (closes[-1]-closes[-2])/closes[-2] if len(closes)>=2 else 0
    ret_5d = (closes[-1]-closes[-6])/closes[-6] if len(closes)>=6 else 0
    ret_20d= (closes[-1]-closes[-21])/closes[-21] if len(closes)>=21 else 0
    if ret_1d > 0.005 and ret_5d > 0: score += 2
    if ret_20d > 0.02: score += 1

    # Turtle breakout
    if len(closes) >= 21:
        high20 = max(closes[-21:-1])
        if closes[-1] > high20: score += 2

    # Trend filter
    if ind["ema_trend"] == "BULLISH": score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if ind["rsi"] > 50: score += 1

    if score >= min_score: return "BUY"
    return "HOLD"

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run_asset(name, symbol, asset_type, sl, tp, strategies):
    print(f"\n{'='*115}")
    print(f"  {name} ({symbol}) | SL:{sl}% TP:{tp}% LEV:{LEVERAGE}x")
    print(f"{'='*115}")

    results = {}
    for period, start, end, years in [
        ("In-Sample   2015-2020", "2015-01-01", "2020-01-01", 5),
        ("Out-of-Sample 2020-2024", "2020-01-01", "2024-12-31", 4),
        ("Full 2015-2024",          "2015-01-01", "2024-12-31", 10),
    ]:
        print(f"\n  📅 {period}")
        print(f"  {'─'*112}")
        df = load_data(asset_type, symbol, start, end, timeframe="1d")
        if df is None or len(df) < 300:
            print("  ❌ Data tidak cukup"); continue

        bh_r = bh(df, LEVERAGE, years)
        print(f"  {'B&H 3x (benchmark)':<38} | CAGR:{bh_r['cagr']:6.1f}%   "
              f"| DD:{bh_r['dd']:6.1f}% | Sharpe:{bh_r['sharpe']:5.2f}    "
              f"| (target to beat)")
        print(f"  {'─'*112}")

        period_res = {}
        for label, fn in strategies:
            try:
                r = backtest(df, sl, tp, LEVERAGE, fn, years)
                period_res[label] = r
                prow(label, r, bh_r["cagr"])
            except Exception as e:
                print(f"  {label:<38} | ERROR: {e}")

        results[period] = (period_res, bh_r["cagr"])

    # Scoring konsistensi
    print(f"\n  {'─'*112}")
    print(f"  📊 CONSISTENCY SCORE (in-sample + out-of-sample):")
    scores = {}
    for label, _ in strategies:
        score = 0
        for period in ["In-Sample   2015-2020", "Out-of-Sample 2020-2024"]:
            if period not in results: continue
            pr, bh_cagr = results[period]
            if label not in pr: continue
            r = pr[label]
            if r["cagr"] > bh_cagr:  score += 3
            if r["sharpe"] > 0.8:    score += 2
            if r["calmar"] > 0.5:    score += 1
            if r["dd"] > -60:        score += 1
        scores[label] = score

    for label, sc in sorted(scores.items(), key=lambda x: -x[1]):
        bar = "█"*sc + "░"*(14-min(sc,14))
        print(f"     {label:<38} | Score:{sc:2d}/14 | {bar}")

    best = max(scores, key=scores.get)
    print(f"\n  🏆 PALING KONSISTEN: {best} (Score:{scores[best]}/14)")
    return scores, best, results

if __name__ == "__main__":
    print("\n"+"="*115)
    print("  RESEARCH-BACKED STRATEGY BACKTEST (SSRN Papers)")
    print(f"  Periode: {START}→{END} | Leverage:{LEVERAGE}x")
    print("  Sources: Zarattini 2024, Huang 2024, Drogen 2023, Gold Seasonality, SPX Seasonality")
    print("="*115)

    # BTC
    btc_strats = [
        ("Baseline Momentum",          btc_baseline),
        ("R1: Short Momentum 30d/7d",   btc_short_momentum),
        ("R2: Volume-Weighted TSMOM",   btc_volume_weighted_momentum),
        ("R3: Abnormal Return Filter",  btc_abnormal_return),
        ("R4: Combined BTC Research",   btc_combined_research),
    ]
    sc_btc, best_btc, res_btc = run_asset(
        "Bitcoin", "BTC/USDT", "crypto", 6.0, 30.0, btc_strats)

    # Gold
    gold_strats = [
        ("Baseline Adaptive",           gold_baseline),
        ("R5: Seasonal Filter",         gold_seasonal),
        ("R6: Combined Gold Research",  gold_combined_research),
    ]
    sc_gold, best_gold, res_gold = run_asset(
        "Gold", "GC=F", "stock", 8.0, 30.0, gold_strats)

    # SPX
    spx_strats = [
        ("Baseline Turtle",             spx_baseline),
        ("R7: Sell-in-May",             spx_sell_in_may),
        ("R8: Monthly Seasonal",        spx_monthly_seasonal),
        ("R9: Turn-of-Month",           spx_turn_of_month),
        ("R10: Demand Imbalance",       spx_demand_imbalance),
        ("R11: Combined SPX Research",  spx_combined_research),
    ]
    sc_spx, best_spx, res_spx = run_asset(
        "S&P 500", "^GSPC", "stock", 10.0, 30.0, spx_strats)

    # Summary final
    print("\n"+"="*115)
    print("  RINGKASAN FINAL — RESEARCH-BACKED vs BASELINE")
    print("="*115)
    for name, scores, best, results in [
        ("Bitcoin",  sc_btc,  best_btc,  res_btc),
        ("Gold",     sc_gold, best_gold, res_gold),
        ("S&P 500",  sc_spx,  best_spx,  res_spx),
    ]:
        full = "Full 2015-2024"
        if full in results:
            pr, bh_cagr = results[full]
            best_r = pr.get(best, {})
            beat = "✅ BEAT" if best_r.get("cagr",0) > bh_cagr else "❌"
            print(f"  {name:10} | B&H:{bh_cagr:6.1f}% | "
                  f"Best:{best_r.get('cagr',0):6.1f}% ({best}) | "
                  f"Sharpe:{best_r.get('sharpe',0):5.2f} | {beat}")

    print("""
  ─────────────────────────────────────────────────────────────────
  📚 RESEARCH SOURCES:
  R1-R4 BTC: Drogen 2023 (cross-sectional momentum), Huang 2024
             (volume-weighted TSMOM), abnormal return intraday paper
  R5-R6 Gold: Gold Market Timing (Bartsch et al), Calendar Anomalies
              (no Monday, Jul-Feb bull season)
  R7-R11 SPX: Zarattini 2024 (demand imbalance, Sharpe 1.33),
               Sell-in-May (300yr data, 80%+ win rate),
               Composite Seasonal (Vojtko & Padysak SSRN),
               Monthly seasonality (Apr/Jul/Nov=80% green)
  ─────────────────────────────────────────────────────────────────
    """)