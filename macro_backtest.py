# macro_backtest.py
# Macro-Enhanced Backtest: tambah DXY, VIX, Yield Curve, Real Rates, M2
# Data sources: yfinance (semua gratis)
# Research: Gold(real rates+VIX+DXY), BTC(M2+DXY+FnG), SPX(VIX+yield curve)

import sys, os
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
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

def sortino(equity, years=YEARS):
    eq = np.array(equity)
    if len(eq) < 2: return 0.0
    dr = np.diff(eq)/eq[:-1]
    dv = dr[dr<0].std()
    if dv == 0: return 0.0
    ar = (eq[-1]/eq[0])**(1/years)-1
    return round((ar-RF_RATE)/(dv*np.sqrt(252)), 2)

def max_dd(equity):
    eq = np.array(equity)
    pk = np.maximum.accumulate(eq)
    return round(float(((eq-pk)/pk*100).min()), 1)

def calmar(c, dd):
    return round(c/abs(dd), 3) if dd != 0 else 0.0

def winrate(trades):
    if not trades: return 0.0
    return round(sum(1 for t in trades if t>0)/len(trades)*100, 1)

def metrics(equity, pnls, years=YEARS):
    c  = cagr(equity[-1], years)
    dd = max_dd(equity)
    return {"cagr":c,"final":round(equity[-1],2),"dd":dd,
            "sharpe":sharpe(equity,years),"sortino":sortino(equity,years),
            "calmar":calmar(c,dd),"wr":winrate(pnls),"trades":len(pnls)}

def bh(df, lev=LEVERAGE, years=YEARS):
    s  = df["close"].iloc[0]
    eq = [max(INITIAL*(1+(p-s)/s*lev), 0.01) for p in df["close"]]
    c  = cagr(eq[-1], years)
    return {"cagr":c,"dd":max_dd(eq),"sharpe":sharpe(eq,years)}

def prow(label, r, bh_cagr, w=42):
    beat = "✅" if r["cagr"] > bh_cagr else "❌"
    sg   = "🟢" if r["sharpe"]>1.5 else ("🟡" if r["sharpe"]>0.8 else "🔴")
    print(f"  {label:<{w}} | CAGR:{r['cagr']:6.1f}%{beat}"
          f" | DD:{r['dd']:6.1f}%"
          f" | Sharpe:{r['sharpe']:5.2f}{sg}"
          f" | Sortino:{r['sortino']:5.2f}"
          f" | Calmar:{r['calmar']:5.3f}"
          f" | WR:{r['wr']:5.1f}% | T:{r['trades']}")

# ─── Macro Data Loader ────────────────────────────────────────────────────────

print("📥 Loading macro data dari yfinance...")

def load_macro(start=START, end=END):
    """
    Load semua macro data sekaligus.
    Returns dict of DataFrames indexed by date.
    """
    macro = {}
    tickers = {
        "DXY":   "DX-Y.NYB",   # Dollar Index
        "VIX":   "^VIX",       # Fear gauge
        "TNX":   "^TNX",       # 10Y Treasury yield
        "IRX":   "^IRX",       # 3-month T-bill (untuk yield curve)
        "M2":    None,          # M2 dari FRED (proxy via yf tidak tersedia langsung)
    }

    for name, ticker in tickers.items():
        if ticker is None: continue
        try:
            df = yf.download(ticker, start=start, end=end,
                             auto_adjust=True, progress=False)
            if df is not None and len(df) > 100:
                macro[name] = df["Close"].squeeze()
                print(f"  ✅ {name} ({ticker}): {len(df)} rows")
            else:
                print(f"  ⚠️ {name}: data kosong")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    # Yield curve = 10Y - 3M (proxy resesi dari SSRN Hansen 2022)
    if "TNX" in macro and "IRX" in macro:
        tnx = macro["TNX"].reindex(macro["IRX"].index, method="ffill")
        macro["YIELD_CURVE"] = tnx - macro["IRX"]
        print(f"  ✅ YIELD_CURVE (10Y-3M): computed")

    # Real rate proxy = 10Y yield - rolling 12m CPI change (approx dari price level)
    # Gunakan TNX saja sebagai proxy (karena CPI data sulit di yfinance)
    # Real rate tinggi → bearish gold, real rate rendah → bullish gold

    return macro

MACRO = load_macro()

def get_macro_on_date(date):
    """Ambil nilai macro pada tanggal tertentu"""
    result = {}
    ts = pd.Timestamp(date)
    for name, series in MACRO.items():
        try:
            # Cari nilai terdekat sebelum atau pada tanggal ini
            idx = series.index[series.index <= ts]
            if len(idx) > 0:
                result[name] = float(series[idx[-1]])
            else:
                result[name] = None
        except:
            result[name] = None
    return result

def get_macro_trend(date, lookback=20):
    """Hitung tren macro dalam N hari terakhir"""
    ts  = pd.Timestamp(date)
    ago = ts - timedelta(days=lookback*2)
    result = {}
    for name, series in MACRO.items():
        try:
            subset = series[(series.index >= ago) & (series.index <= ts)]
            if len(subset) >= 5:
                recent = float(subset.iloc[-1])
                past   = float(subset.iloc[max(0, len(subset)-lookback)])
                result[f"{name}_trend"] = "UP" if recent > past else "DOWN"
                result[f"{name}_val"]   = recent
            else:
                result[f"{name}_trend"] = "UNKNOWN"
                result[f"{name}_val"]   = None
        except:
            result[f"{name}_trend"] = "UNKNOWN"
            result[f"{name}_val"]   = None
    return result

# ─── Backtest Engine ──────────────────────────────────────────────────────────

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

        macro = get_macro_trend(date)
        sig   = signal_fn(ind, closes[:i+1], date, volumes[:i+1], macro, **kw)

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
                pos = {"t":"long","e":price,"q":(balance*lev)/price,"a":balance}
                balance = 0
            elif sig == "SELL":
                pos = {"t":"short","e":price,"q":(balance*lev)/price,"a":balance}
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
# GOLD MACRO STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

def gold_baseline(ind, closes, date, vols, macro, **kw):
    """Baseline: adaptive teknikal saja (tanpa macro)"""
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
            if price > high20 and ind["ema_trend"] == "BULLISH":
                return "BUY"
    else:
        s50 = pd.Series(closes[-50:])
        ma  = float(s50.rolling(20).mean().iloc[-1])
        std = float(s50.rolling(20).std().iloc[-1])
        if std > 0:
            z = (closes[-1]-ma)/std
            if z < -2.2 and ind["rsi"] < 40 and ind["bb_pos"] == "OVERSOLD":
                return "BUY"
    return "HOLD"

def gold_macro_dxy_vix(ind, closes, date, vols, macro, **kw):
    """
    Research: DXY + VIX + Real Rates untuk Gold
    Gold bullish ketika: DXY turun + VIX naik + yields turun
    Gold bearish ketika: DXY naik + VIX turun + yields naik
    """
    if len(closes) < 200: return "HOLD"

    dxy_trend = macro.get("DXY_trend", "UNKNOWN")
    vix_trend = macro.get("VIX_trend", "UNKNOWN")
    tnx_trend = macro.get("TNX_trend", "UNKNOWN")
    vix_val   = macro.get("VIX_val")

    # Macro score untuk gold
    macro_score = 0
    if dxy_trend == "DOWN":  macro_score += 2   # DXY turun = bullish gold
    elif dxy_trend == "UP":  macro_score -= 2
    if vix_trend == "UP":    macro_score += 1   # VIX naik = safe haven demand
    elif vix_trend == "DOWN": macro_score -= 1
    if tnx_trend == "DOWN":  macro_score += 1   # Yields turun = bullish gold
    elif tnx_trend == "UP":  macro_score -= 1

    # Extra: VIX di atas 20 = risk-off = bullish gold
    if vix_val and vix_val > 20: macro_score += 1
    if vix_val and vix_val > 30: macro_score += 1  # Extreme fear

    # Technical score
    s      = pd.Series(closes)
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

    # Turtle dalam trending
    if is_trending and len(closes) >= 21:
        high20 = max(closes[-21:-1])
        if price > high20: tech_score += 2

    # Mean reversion dalam sideways
    if not is_trending:
        s50 = pd.Series(closes[-50:])
        ma  = float(s50.rolling(20).mean().iloc[-1])
        std = float(s50.rolling(20).std().iloc[-1])
        if std > 0:
            z = (closes[-1]-ma)/std
            if z < -2.0: tech_score += 2
            elif z > 2.0: tech_score -= 2

    # Kombinasi: butuh macro DAN teknikal setuju
    total = macro_score + tech_score
    if total >= 4 and macro_score >= 1:  return "BUY"
    if total <= -4 and macro_score <= -1: return "SELL"
    return "HOLD"

def gold_macro_yield_curve(ind, closes, date, vols, macro, **kw):
    """
    Research: Yield Curve (10Y-3M) sebagai macro filter untuk Gold
    Yield curve inverted = recession risk = bullish gold
    Yield curve steep = growth = neutral/bearish gold
    """
    if len(closes) < 200: return "HOLD"

    yc_val    = macro.get("YIELD_CURVE_val")
    yc_trend  = macro.get("YIELD_CURVE_trend", "UNKNOWN")
    dxy_trend = macro.get("DXY_trend", "UNKNOWN")
    tnx_trend = macro.get("TNX_trend", "UNKNOWN")

    macro_score = 0
    if yc_val is not None:
        if yc_val < 0:    macro_score += 2  # Inverted = recession = bullish gold
        elif yc_val < 0.5: macro_score += 1
    if yc_trend == "DOWN": macro_score += 1  # Curve flattening = gold bullish
    if dxy_trend == "DOWN": macro_score += 1
    if tnx_trend == "DOWN": macro_score += 1

    # Seasonal Gold (Juli-Feb = bull season)
    month = pd.Timestamp(date).month if hasattr(date, "month") else date.month
    weekday = pd.Timestamp(date).weekday()
    GOLD_BULL = [7,8,9,10,11,12,1,2]
    if weekday == 0: return "HOLD"  # No Monday
    if month in GOLD_BULL: macro_score += 1

    # Technical
    s      = pd.Series(closes)
    ret_3m = (closes[-1]-closes[-63])/closes[-63] if len(closes)>=63 else 0
    vol_20 = float(pd.Series(closes[-20:]).pct_change().std()*np.sqrt(252))
    is_trending = abs(ret_3m) > 0.08 and vol_20 > 0.12

    tech_score = 0
    if ind["ema_trend"] == "BULLISH": tech_score += 2
    elif ind["ema_trend"] == "BEARISH": tech_score -= 2
    if ind["macd_cross"] == "BULLISH": tech_score += 1
    else: tech_score -= 1

    if is_trending and len(closes) >= 21:
        high20 = max(closes[-21:-1])
        if closes[-1] > high20: tech_score += 2

    if not is_trending:
        s50 = pd.Series(closes[-50:])
        ma  = float(s50.rolling(20).mean().iloc[-1])
        std = float(s50.rolling(20).std().iloc[-1])
        if std > 0:
            z = (closes[-1]-ma)/std
            if z < -2.0: tech_score += 2
            elif z > 2.0: tech_score -= 2

    total = macro_score + tech_score
    if total >= 5 and macro_score >= 2: return "BUY"
    if total <= -3 and macro_score <= 0: return "SELL"
    return "HOLD"

def gold_macro_full(ind, closes, date, vols, macro, **kw):
    """
    FULL MACRO GOLD: DXY + VIX + Yield Curve + Real Rates +
    Seasonal + Day-of-week + Adaptive teknikal
    Semua faktor dikombinasikan
    """
    if len(closes) < 200: return "HOLD"

    # Day-of-week: no Monday
    weekday = pd.Timestamp(date).weekday()
    if weekday == 0: return "HOLD"

    # Seasonal
    month = pd.Timestamp(date).month
    GOLD_BULL = [7,8,9,10,11,12,1,2]
    GOLD_BEAR = [3,4,5,6]
    bull_season = month in GOLD_BULL
    bear_season = month in GOLD_BEAR

    # Macro factors
    dxy_trend = macro.get("DXY_trend", "UNKNOWN")
    vix_trend = macro.get("VIX_trend", "UNKNOWN")
    vix_val   = macro.get("VIX_val")
    tnx_trend = macro.get("TNX_trend", "UNKNOWN")
    yc_val    = macro.get("YIELD_CURVE_val")
    yc_trend  = macro.get("YIELD_CURVE_trend", "UNKNOWN")

    macro_score = 0
    # DXY (weight: 2)
    if dxy_trend == "DOWN": macro_score += 2
    elif dxy_trend == "UP": macro_score -= 2
    # VIX (weight: 1-2)
    if vix_trend == "UP":   macro_score += 1
    if vix_val and vix_val > 20: macro_score += 1
    if vix_val and vix_val > 30: macro_score += 1
    # Yields (weight: 1)
    if tnx_trend == "DOWN": macro_score += 1
    elif tnx_trend == "UP": macro_score -= 1
    # Yield curve (weight: 1-2)
    if yc_val is not None and yc_val < 0:    macro_score += 2
    elif yc_val is not None and yc_val < 0.5: macro_score += 1
    if yc_trend == "DOWN": macro_score += 1
    # Seasonal (weight: 1)
    if bull_season: macro_score += 1
    elif bear_season: macro_score -= 1

    # Technical score
    s       = pd.Series(closes)
    ema200  = float(s.ewm(span=200).mean().iloc[-1])
    price   = closes[-1]
    ret_3m  = (closes[-1]-closes[-63])/closes[-63] if len(closes)>=63 else 0
    ret_1m  = (closes[-1]-closes[-21])/closes[-21] if len(closes)>=21 else 0
    vol_20  = float(pd.Series(closes[-20:]).pct_change().std()*np.sqrt(252))
    is_trending    = abs(ret_3m) > 0.08 and vol_20 > 0.12
    prolonged_bear = ret_3m < -0.08 and ret_1m < -0.03

    if prolonged_bear and bear_season: return "HOLD"

    tech_score = 0
    if ind["ema_trend"] == "BULLISH": tech_score += 2
    elif ind["ema_trend"] == "BEARISH": tech_score -= 2
    if ind["macd_cross"] == "BULLISH": tech_score += 1
    else: tech_score -= 1
    if ind["rsi"] < 35: tech_score += 1
    elif ind["rsi"] > 65: tech_score -= 1

    if is_trending and len(closes) >= 21:
        high20 = max(closes[-21:-1])
        if price > high20: tech_score += 2

    if not is_trending:
        s50 = pd.Series(closes[-50:])
        ma  = float(s50.rolling(20).mean().iloc[-1])
        std = float(s50.rolling(20).std().iloc[-1])
        if std > 0:
            z = (closes[-1]-ma)/std
            rsi_ok   = ind["rsi"] < 38
            stoch_ok = ind["stoch_signal"] == "OVERSOLD"
            bb_ok    = ind["bb_pos"] == "OVERSOLD"
            if z < -2.0 and sum([rsi_ok,stoch_ok,bb_ok]) >= 2:
                tech_score += 2
            if z > 2.2 and ind["rsi"] > 62:
                tech_score -= 2

    total = macro_score + tech_score
    # Entry membutuhkan macro positif DAN teknikal mendukung
    if total >= 6 and macro_score >= 2 and tech_score >= 1: return "BUY"
    if total <= -4 and macro_score <= -1: return "SELL"
    return "HOLD"

# ═══════════════════════════════════════════════════════════════════════════
# BTC MACRO STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

def btc_baseline(ind, closes, date, vols, macro, **kw):
    """Baseline: Volume-Weighted TSMOM (terbaik dari backtest sebelumnya)"""
    if len(closes) < 30 or len(vols) < 20: return "HOLD"
    ret_30d = (closes[-1]-closes[-30])/closes[-30]
    ret_7d  = (closes[-1]-closes[-7])/closes[-7]
    vol_ratio = vols[-1]/(np.median(vols[-20:])+1e-9)
    vol_strong = vol_ratio > 1.2

    score = 0
    if ret_30d > 0: score += 2
    if ret_7d  > 0: score += 1
    if ind["ema_trend"] == "BULLISH": score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if vol_strong: score += 2

    if score >= 5: return "BUY"
    if score <= -3: return "SELL"
    return "HOLD"

def btc_macro_dxy_m2(ind, closes, date, vols, macro, **kw):
    """
    Research: M2 + DXY untuk BTC
    BTC → DXY turun = bullish (inverse correlation)
    BTC → M2 global naik = bullish (liquidity driver)
    Proxy M2: gunakan DXY turun + yields turun sebagai liquidity proxy
    """
    if len(closes) < 30 or len(vols) < 20: return "HOLD"

    dxy_trend = macro.get("DXY_trend", "UNKNOWN")
    tnx_trend = macro.get("TNX_trend", "UNKNOWN")
    vix_val   = macro.get("VIX_val")

    # Macro score untuk BTC
    macro_score = 0
    if dxy_trend == "DOWN":  macro_score += 3   # DXY turun = bullish BTC (kuat)
    elif dxy_trend == "UP":  macro_score -= 3
    if tnx_trend == "DOWN":  macro_score += 1   # Yields turun = liquidity up
    elif tnx_trend == "UP":  macro_score -= 1
    # BTC = risk asset: VIX tinggi = bearish BTC
    if vix_val and vix_val < 20: macro_score += 1
    elif vix_val and vix_val > 25: macro_score -= 1
    elif vix_val and vix_val > 35: macro_score -= 2

    # Technical (Volume-Weighted TSMOM)
    ret_30d    = (closes[-1]-closes[-30])/closes[-30]
    ret_7d     = (closes[-1]-closes[-7])/closes[-7]
    vol_ratio  = vols[-1]/(np.median(vols[-20:])+1e-9)
    vol_strong = vol_ratio > 1.2

    tech_score = 0
    if ret_30d > 0: tech_score += 2
    if ret_7d  > 0: tech_score += 1
    if ind["ema_trend"] == "BULLISH": tech_score += 2
    if ind["macd_cross"] == "BULLISH": tech_score += 1
    if vol_strong: tech_score += 1

    total = macro_score + tech_score
    if total >= 6 and macro_score >= 1: return "BUY"
    if total <= -4 and macro_score <= -1: return "SELL"
    return "HOLD"

def btc_macro_fear_greed(ind, closes, date, vols, macro, **kw):
    """
    Research: Fear & Greed + Regime UP-UP untuk BTC momentum
    Momentum BTC hanya profitable di UP-UP regime (paper 2024)
    """
    if len(closes) < 30 or len(vols) < 20: return "HOLD"

    vix_val   = macro.get("VIX_val")
    dxy_trend = macro.get("DXY_trend", "UNKNOWN")
    vix_trend = macro.get("VIX_trend", "UNKNOWN")

    # Fear proxy: VIX sebagai inverse fear gauge untuk BTC
    # BTC naik ketika greed (VIX rendah + turun)
    fear_score = 0
    if vix_val and vix_val < 15: fear_score = 2    # Extreme greed → BUY
    elif vix_val and vix_val < 20: fear_score = 1  # Greed
    elif vix_val and vix_val > 30: fear_score = -2 # Extreme fear → avoid
    elif vix_val and vix_val > 25: fear_score = -1

    if vix_trend == "DOWN": fear_score += 1  # VIX turun = greed naik
    elif vix_trend == "UP": fear_score -= 1

    # DXY
    if dxy_trend == "DOWN": fear_score += 1
    elif dxy_trend == "UP": fear_score -= 1

    # Regime UP-UP check: BTC dan macro sama-sama bullish
    ret_30d   = (closes[-1]-closes[-30])/closes[-30]
    ret_7d    = (closes[-1]-closes[-7])/closes[-7]
    vol_ratio = vols[-1]/(np.median(vols[-20:])+1e-9)
    up_up     = ret_30d > 0 and ret_7d > 0 and ind["ema_trend"] == "BULLISH"

    tech_score = 0
    if up_up: tech_score += 3
    if ind["macd_cross"] == "BULLISH": tech_score += 1
    if vol_ratio > 1.2: tech_score += 1

    total = fear_score + tech_score
    if total >= 4 and fear_score >= 1 and up_up: return "BUY"
    if total <= -3 and fear_score <= -1: return "SELL"
    return "HOLD"

def btc_macro_full(ind, closes, date, vols, macro, **kw):
    """
    FULL MACRO BTC: DXY + VIX/Fear + Yields + UP-UP Regime +
    Volume-Weighted TSMOM
    """
    if len(closes) < 30 or len(vols) < 20: return "HOLD"

    dxy_trend = macro.get("DXY_trend", "UNKNOWN")
    tnx_trend = macro.get("TNX_trend", "UNKNOWN")
    vix_val   = macro.get("VIX_val")
    vix_trend = macro.get("VIX_trend", "UNKNOWN")

    # Macro score
    macro_score = 0
    if dxy_trend == "DOWN": macro_score += 3
    elif dxy_trend == "UP": macro_score -= 3
    if tnx_trend == "DOWN": macro_score += 1
    elif tnx_trend == "UP": macro_score -= 1
    if vix_val:
        if vix_val < 15:    macro_score += 2
        elif vix_val < 20:  macro_score += 1
        elif vix_val > 30:  macro_score -= 2
        elif vix_val > 25:  macro_score -= 1
    if vix_trend == "DOWN": macro_score += 1
    elif vix_trend == "UP": macro_score -= 1

    # Technical
    ret_30d   = (closes[-1]-closes[-30])/closes[-30]
    ret_7d    = (closes[-1]-closes[-7])/closes[-7]
    vol_ratio = vols[-1]/(np.median(vols[-20:])+1e-9)
    up_up     = ret_30d > 0 and ret_7d > 0 and ind["ema_trend"] == "BULLISH"

    tech_score = 0
    if up_up:  tech_score += 3
    if ind["macd_cross"] == "BULLISH": tech_score += 1
    if vol_ratio > 1.2: tech_score += 1
    if ind["rsi"] < 35: tech_score += 1

    total = macro_score + tech_score
    if total >= 7 and macro_score >= 2 and up_up: return "BUY"
    if total <= -4 and macro_score <= -2: return "SELL"
    return "HOLD"

# ═══════════════════════════════════════════════════════════════════════════
# SPX MACRO STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

def spx_baseline(ind, closes, date, vols, macro, **kw):
    """Baseline: Monthly Seasonal (R8, terbaik dari backtest sebelumnya)"""
    if len(closes) < 21: return "HOLD"
    month = pd.Timestamp(date).month
    WEAK_MONTHS = [6, 9]
    STRONG_MONTHS = [1,4,7,11]
    if month in WEAK_MONTHS: return "HOLD"

    score = 0
    high20 = max(closes[-21:-1])
    if closes[-1] > high20: score += 3
    if ind["ema_trend"] == "BULLISH": score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if ind["rsi"] > 50: score += 1
    if month in STRONG_MONTHS: score += 1

    if score >= 5: return "BUY"
    return "HOLD"

def spx_macro_vix_regime(ind, closes, date, vols, macro, **kw):
    """
    Research: VIX + EMA200 Regime untuk SPX (Hansen SSRN 2022)
    SPX di atas EMA200 = bull regime → hanya long
    VIX-yield curve cycle untuk timing entry/exit
    """
    if len(closes) < 210: return "HOLD"

    vix_val   = macro.get("VIX_val")
    vix_trend = macro.get("VIX_trend", "UNKNOWN")
    yc_val    = macro.get("YIELD_CURVE_val")
    month     = pd.Timestamp(date).month
    WEAK      = [6,9]

    if month in WEAK: return "HOLD"

    # EMA200 regime (dari SSRN paper)
    s      = pd.Series(closes)
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]
    above_ema200 = price > ema200

    # VIX regime score
    macro_score = 0
    if above_ema200:
        macro_score += 2  # Bull regime baseline
    else:
        macro_score -= 2  # Bear regime

    if vix_val:
        if vix_val < 15:   macro_score += 2  # Low vol = risk-on
        elif vix_val < 20: macro_score += 1
        elif vix_val > 30: macro_score -= 2  # High fear = avoid long
        elif vix_val > 25: macro_score -= 1

    # Yield curve: inverted = recession warning
    if yc_val is not None:
        if yc_val < 0:     macro_score -= 2  # Inverted = bad for stocks
        elif yc_val > 1.0: macro_score += 1  # Steep = healthy

    # Seasonal
    STRONG = [1,4,7,11]
    WINTER = [11,12,1,2,3,4]
    if month in WINTER: macro_score += 1
    if month in STRONG: macro_score += 1

    # Technical
    tech_score = 0
    if len(closes) >= 21:
        high20 = max(closes[-21:-1])
        if price > high20: tech_score += 2
    if ind["ema_trend"] == "BULLISH": tech_score += 2
    if ind["macd_cross"] == "BULLISH": tech_score += 1

    total = macro_score + tech_score
    if total >= 5 and macro_score >= 2 and above_ema200: return "BUY"
    return "HOLD"

def spx_macro_yield_curve(ind, closes, date, vols, macro, **kw):
    """
    Research: Yield Curve recession predictor untuk SPX timing
    Inverted yield curve → kurangi exposure / keluar
    Steep yield curve + bull regime → full exposure
    """
    if len(closes) < 210: return "HOLD"

    yc_val  = macro.get("YIELD_CURVE_val")
    yc_trend = macro.get("YIELD_CURVE_trend", "UNKNOWN")
    vix_val  = macro.get("VIX_val")
    month    = pd.Timestamp(date).month
    WEAK     = [6,9]
    if month in WEAK: return "HOLD"

    # Yield curve filter: hindari entry saat inverted
    if yc_val is not None and yc_val < -0.5:
        return "HOLD"  # Inverted curve = recession signal = keluar

    macro_score = 0
    if yc_val is not None:
        if yc_val > 1.0:   macro_score += 2
        elif yc_val > 0:   macro_score += 1
    if yc_trend == "UP":   macro_score += 1
    if vix_val and vix_val < 20: macro_score += 1
    elif vix_val and vix_val > 25: macro_score -= 1

    WINTER = [11,12,1,2,3,4]
    STRONG = [1,4,7,11]
    if month in WINTER: macro_score += 1
    if month in STRONG: macro_score += 1

    s      = pd.Series(closes)
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]

    tech_score = 0
    if price > ema200: tech_score += 2
    if len(closes) >= 21:
        high20 = max(closes[-21:-1])
        if price > high20: tech_score += 2
    if ind["ema_trend"] == "BULLISH": tech_score += 2
    if ind["macd_cross"] == "BULLISH": tech_score += 1

    total = macro_score + tech_score
    if total >= 6 and macro_score >= 1: return "BUY"
    return "HOLD"

def spx_macro_full(ind, closes, date, vols, macro, **kw):
    """
    FULL MACRO SPX: VIX regime + Yield Curve + EMA200 +
    Seasonal (Sell-in-May + Monthly) + Demand Imbalance
    """
    if len(closes) < 210: return "HOLD"

    vix_val  = macro.get("VIX_val")
    vix_trend = macro.get("VIX_trend", "UNKNOWN")
    yc_val   = macro.get("YIELD_CURVE_val")
    yc_trend = macro.get("YIELD_CURVE_trend", "UNKNOWN")
    dxy_trend = macro.get("DXY_trend", "UNKNOWN")

    month   = pd.Timestamp(date).month
    day     = pd.Timestamp(date).day
    WEAK    = [6,9]
    SUMMER  = [5,6,7,8,9,10]
    WINTER  = [11,12,1,2,3,4]
    STRONG  = [1,4,7,11]

    if month in WEAK: return "HOLD"

    # Yield curve hard filter
    if yc_val is not None and yc_val < -0.5: return "HOLD"

    # Macro score
    macro_score = 0
    if yc_val is not None:
        if yc_val > 1.0:   macro_score += 2
        elif yc_val > 0:   macro_score += 1
        elif yc_val < 0:   macro_score -= 1
    if yc_trend == "UP": macro_score += 1
    if vix_val:
        if vix_val < 15:   macro_score += 2
        elif vix_val < 20: macro_score += 1
        elif vix_val > 25: macro_score -= 1
        elif vix_val > 30: macro_score -= 2
    if vix_trend == "DOWN": macro_score += 1
    if dxy_trend == "DOWN": macro_score += 1  # Weak USD = risk-on

    # Seasonal
    if month in WINTER: macro_score += 1
    if month in STRONG: macro_score += 1
    if day >= 28 or day <= 3: macro_score += 1  # Turn-of-month

    # Summer: threshold lebih tinggi
    min_total = 8 if month in SUMMER else 5

    # Technical
    s      = pd.Series(closes)
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]

    tech_score = 0
    if price > ema200: tech_score += 2
    if len(closes) >= 21:
        high20 = max(closes[-21:-1])
        if price > high20: tech_score += 2
    if ind["ema_trend"] == "BULLISH": tech_score += 2
    if ind["macd_cross"] == "BULLISH": tech_score += 1
    # Demand imbalance
    ret_1d = (closes[-1]-closes[-2])/closes[-2] if len(closes)>=2 else 0
    ret_5d = (closes[-1]-closes[-6])/closes[-6] if len(closes)>=6 else 0
    if ret_1d > 0.005 and ret_5d > 0: tech_score += 1

    total = macro_score + tech_score
    if total >= min_total and macro_score >= 2 and price > ema200: return "BUY"
    return "HOLD"

# ─── Main ─────────────────────────────────────────────────────────────────────

def run_asset(name, symbol, asset_type, sl, tp, strategies):
    print(f"\n{'='*118}")
    print(f"  {name} ({symbol}) | SL:{sl}% TP:{tp}% LEV:{LEVERAGE}x")
    print(f"{'='*118}")

    all_results = {}
    for period, start, end, years in [
        ("In-Sample   2015-2020", "2015-01-01","2020-01-01", 5),
        ("Out-of-Sample 2020-2024","2020-01-01","2024-12-31", 4),
        ("Full 2015-2024",        "2015-01-01","2024-12-31",10),
    ]:
        print(f"\n  📅 {period}")
        print(f"  {'─'*115}")
        df = load_data(asset_type, symbol, start, end, timeframe="1d")
        if df is None or len(df) < 300:
            print("  ❌ Data tidak cukup"); continue

        bh_r = bh(df, LEVERAGE, years)
        print(f"  {'B&H 3x':<42} | CAGR:{bh_r['cagr']:6.1f}%   "
              f"| DD:{bh_r['dd']:6.1f}% | Sharpe:{bh_r['sharpe']:5.2f}")
        print(f"  {'─'*115}")

        period_res = {}
        for label, fn in strategies:
            try:
                r = backtest(df, sl, tp, LEVERAGE, fn, years)
                period_res[label] = r
                prow(label, r, bh_r["cagr"])
            except Exception as e:
                print(f"  {label:<42} | ERROR: {e}")
        all_results[period] = (period_res, bh_r["cagr"])

    # Scoring
    print(f"\n  {'─'*115}")
    print(f"  📊 CONSISTENCY SCORE (in-sample + out-of-sample):")
    scores = {}
    for label, _ in strategies:
        score = 0
        for period in ["In-Sample   2015-2020","Out-of-Sample 2020-2024"]:
            if period not in all_results: continue
            pr, bh_cagr = all_results[period]
            if label not in pr: continue
            r = pr[label]
            if r["cagr"] > bh_cagr: score += 3
            if r["sharpe"] > 0.8:   score += 2
            if r["calmar"] > 0.5:   score += 1
            if r["dd"] > -60:       score += 1
        scores[label] = score

    for label, sc in sorted(scores.items(), key=lambda x: -x[1]):
        bar = "█"*sc + "░"*(14-min(sc,14))
        print(f"     {label:<42} | Score:{sc:2d}/14 | {bar}")

    best = max(scores, key=scores.get)
    print(f"\n  🏆 PALING KONSISTEN: {best} (Score:{scores[best]}/14)")
    return scores, best, all_results

if __name__ == "__main__":
    print("\n"+"="*118)
    print("  MACRO-ENHANCED STRATEGY BACKTEST")
    print(f"  Periode: {START}→{END} | Leverage:{LEVERAGE}x")
    print("  Macro Data: DXY, VIX, 10Y Yield, Yield Curve (gratis via yfinance)")
    print("  Research: Real rates+VIX+DXY (Gold), M2+DXY+FnG (BTC), VIX+YieldCurve (SPX)")
    print("="*118)

    gold_strats = [
        ("Baseline (teknikal saja)",       gold_baseline),
        ("M1: DXY + VIX + Real Rates",     gold_macro_dxy_vix),
        ("M2: Yield Curve + Seasonal",     gold_macro_yield_curve),
        ("M3: Full Macro Gold",            gold_macro_full),
    ]
    sc_gold, best_gold, res_gold = run_asset(
        "Gold", "GC=F", "stock", 8.0, 30.0, gold_strats)

    btc_strats = [
        ("Baseline (Vol-Weighted TSMOM)",   btc_baseline),
        ("M4: DXY + M2 Proxy",             btc_macro_dxy_m2),
        ("M5: Fear&Greed + UP-UP Regime",  btc_macro_fear_greed),
        ("M6: Full Macro BTC",             btc_macro_full),
    ]
    sc_btc, best_btc, res_btc = run_asset(
        "Bitcoin", "BTC/USDT", "crypto", 6.0, 30.0, btc_strats)

    spx_strats = [
        ("Baseline (Monthly Seasonal)",    spx_baseline),
        ("M7: VIX + EMA200 Regime",        spx_macro_vix_regime),
        ("M8: Yield Curve Filter",         spx_macro_yield_curve),
        ("M9: Full Macro SPX",             spx_macro_full),
    ]
    sc_spx, best_spx, res_spx = run_asset(
        "S&P 500", "^GSPC", "stock", 10.0, 30.0, spx_strats)

    print("\n"+"="*118)
    print("  RINGKASAN FINAL — MACRO vs BASELINE vs BUY & HOLD")
    print("="*118)
    for name, scores, best, results in [
        ("Gold",    sc_gold, best_gold, res_gold),
        ("Bitcoin", sc_btc,  best_btc,  res_btc),
        ("S&P 500", sc_spx,  best_spx,  res_spx),
    ]:
        full = "Full 2015-2024"
        if full in results:
            pr, bh_cagr = results[full]
            base_r  = pr.get(list(pr.keys())[0], {})
            best_r  = pr.get(best, {})
            beat    = "✅ BEAT" if best_r.get("cagr",0) > bh_cagr else "❌"
            improve = best_r.get("cagr",0) - base_r.get("cagr",0)
            print(f"  {name:10} | B&H:{bh_cagr:6.1f}% | "
                  f"Base:{base_r.get('cagr',0):6.1f}% | "
                  f"Best:{best_r.get('cagr',0):6.1f}% ({best[:25]}) | "
                  f"Macro improvement: {improve:+.1f}% | {beat}")

    print("""
  ─────────────────────────────────────────────────────────────────────────
  📊 MACRO FACTORS USED (semua gratis dari yfinance):
  DXY  (DX-Y.NYB)  : Dollar Index — inverse untuk Gold & BTC
  VIX  (^VIX)      : Fear gauge — negative BTC, positive Gold
  TNX  (^TNX)      : 10Y Treasury yield — real rates proxy
  IRX  (^IRX)      : 3-month T-bill — untuk yield curve (10Y-3M)
  YIELD_CURVE      : TNX-IRX — recession predictor untuk SPX
  ─────────────────────────────────────────────────────────────────────────
    """)