# gold_final_test.py
# Test kombinasi Vol-TSMOM + Monthly Seasonal untuk Gold
# + grid search parameter terbaik

import sys, os
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np
from backtest.data_loader import load_data
from core.indicators import calc_indicators

INITIAL  = 1000.0
LEVERAGE = 3
RF_RATE  = 0.05

# ─── Metrics ─────────────────────────────────────────────────────────────────

def cagr(final, years):
    if final <= 0: return -99.9
    return round(((final/INITIAL)**(1/years)-1)*100, 1)

def sharpe(equity, years):
    eq = np.array(equity)
    if len(eq) < 2: return 0.0
    dr = np.diff(eq)/eq[:-1]
    if dr.std() == 0: return 0.0
    return round(((eq[-1]/eq[0])**(1/years)-1-RF_RATE)/(dr.std()*np.sqrt(252)), 2)

def sortino(equity, years):
    eq = np.array(equity)
    if len(eq) < 2: return 0.0
    dr = np.diff(eq)/eq[:-1]
    dv = dr[dr<0].std()
    if dv == 0: return 0.0
    return round(((eq[-1]/eq[0])**(1/years)-1-RF_RATE)/(dv*np.sqrt(252)), 2)

def max_dd(equity):
    eq = np.array(equity)
    pk = np.maximum.accumulate(eq)
    return round(float(((eq-pk)/pk*100).min()), 1)

def calmar(c, dd):
    return round(c/abs(dd), 3) if dd != 0 else 0.0

def winrate(pnls):
    if not pnls: return 0.0
    return round(sum(1 for p in pnls if p>0)/len(pnls)*100, 1)

def metrics(equity, pnls, years):
    c  = cagr(equity[-1], years)
    dd = max_dd(equity)
    return {"cagr":c, "final":round(equity[-1],2), "dd":dd,
            "sharpe":sharpe(equity,years), "sortino":sortino(equity,years),
            "calmar":calmar(c,dd), "wr":winrate(pnls), "trades":len(pnls)}

def bh_metrics(df, years):
    s  = df["close"].iloc[0]
    eq = [max(INITIAL*(1+(p-s)/s*LEVERAGE), 0.01) for p in df["close"]]
    c  = cagr(eq[-1], years)
    return {"cagr":c, "dd":max_dd(eq), "sharpe":sharpe(eq,years)}

def prow(label, r, bh_cagr, w=45):
    beat = "✅" if r["cagr"] > bh_cagr else "❌"
    sg   = "🟢" if r["sharpe"]>1.5 else ("🟡" if r["sharpe"]>0.8 else "🔴")
    print(f"  {label:<{w}} | CAGR:{r['cagr']:6.1f}%{beat}"
          f" | DD:{r['dd']:6.1f}%"
          f" | Sharpe:{r['sharpe']:5.2f}{sg}"
          f" | Sortino:{r['sortino']:5.2f}"
          f" | Calmar:{r['calmar']:5.3f}"
          f" | WR:{r['wr']:5.1f}% | T:{r['trades']}")

# ─── Backtest Engine ──────────────────────────────────────────────────────────

def backtest(df, sl, tp, sig_fn, years, **kw):
    closes  = df["close"].tolist()
    dates   = list(df.index)
    vols    = df["volume"].tolist() if "volume" in df.columns else [1]*len(closes)
    balance = INITIAL
    pos     = None
    pnls    = []
    equity  = [INITIAL]

    for i in range(252, len(closes)):
        price = closes[i]
        date  = dates[i]
        ind   = calc_indicators(closes[:i+1])
        if ind is None: continue

        sig = sig_fn(ind, closes[:i+1], date, vols[:i+1], **kw)

        if pos:
            pnl_pct = ((price-pos["e"])/pos["e"]*100*LEVERAGE if pos["t"]=="long"
                       else (pos["e"]-price)/pos["e"]*100*LEVERAGE)
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
                pos = {"t":"long","e":price,"q":(balance*LEVERAGE)/price,"a":balance}
                balance = 0
            elif sig == "SELL":
                pos = {"t":"short","e":price,"q":(balance*LEVERAGE)/price,"a":balance}
                balance = 0

    if pos:
        price = closes[-1]
        pnl   = ((price-pos["e"])*pos["q"] if pos["t"]=="long"
                 else (pos["e"]-price)*pos["q"])
        balance += pos["a"] + pnl
        pnls.append(pnl)
        equity.append(balance)

    return metrics(equity, pnls, years)

# ─── Signal Functions ─────────────────────────────────────────────────────────

GOLD_BULL_MONTHS = [7,8,9,10,11,12,1,2]
GOLD_BEAR_MONTHS = [3,4,5,6]

def gold_vol_tsmom(ind, closes, date, vols,
                   lookback=30, vol_pct=60, allow_short=True, **kw):
    """
    Vol-Weighted TSMOM untuk Gold:
    Return N-hari dengan volume weighting
    """
    if len(closes) < lookback+1 or len(vols) < 20: return "HOLD"

    ret_n  = (closes[-1]-closes[-lookback])/closes[-lookback]
    ret_7d = (closes[-1]-closes[-7])/closes[-7] if len(closes)>=7 else 0

    vol_threshold = np.percentile(vols[-50:], vol_pct) if len(vols)>=50 else 0
    vol_ok = vols[-1] >= vol_threshold

    score = 0
    if ret_n  > 0.02: score += 2
    elif ret_n < -0.02: score -= 2
    if ret_7d > 0.01: score += 1
    elif ret_7d < -0.01: score -= 1
    if ind["ema_trend"] == "BULLISH": score += 2
    elif ind["ema_trend"] == "BEARISH": score -= 2
    if ind["macd_cross"] == "BULLISH": score += 1
    else: score -= 1
    if vol_ok: score += 1  # volume confirmation

    if score >= 4: return "BUY"
    if score <= -4 and allow_short: return "SELL"
    return "HOLD"

def gold_monthly_seasonal(ind, closes, date, vols, allow_short=False, **kw):
    """
    Monthly Seasonal untuk Gold (seperti R8 SPX):
    Hanya trade di bull months, skip bear months
    """
    if len(closes) < 50: return "HOLD"
    month   = pd.Timestamp(date).month
    weekday = pd.Timestamp(date).weekday()

    if weekday == 0: return "HOLD"        # No Monday
    if month in GOLD_BEAR_MONTHS: return "HOLD"  # Skip Mar-Jun

    score = 0
    if month in GOLD_BULL_MONTHS: score += 1

    if ind["ema_trend"] == "BULLISH": score += 2
    elif ind["ema_trend"] == "BEARISH": score -= 2
    if ind["macd_cross"] == "BULLISH": score += 1
    else: score -= 1
    if ind["rsi"] < 40: score += 1
    elif ind["rsi"] > 60: score -= 1
    if ind["bb_pos"] == "OVERSOLD": score += 1
    elif ind["bb_pos"] == "OVERBOUGHT": score -= 1

    if score >= 4: return "BUY"
    if score <= -3 and allow_short: return "SELL"
    return "HOLD"

def gold_tsmom_seasonal(ind, closes, date, vols,
                        lookback=30, vol_pct=60,
                        allow_short=False, **kw):
    """
    KOMBINASI: Vol-TSMOM + Monthly Seasonal
    Signal hanya valid kalau:
    1. Berada di bull season (Jul-Feb)
    2. Bukan hari Senin
    3. Vol-TSMOM setuju
    4. Teknikal mendukung
    """
    if len(closes) < lookback+1 or len(vols) < 20: return "HOLD"
    month   = pd.Timestamp(date).month
    weekday = pd.Timestamp(date).weekday()

    # Seasonal filter
    if weekday == 0: return "HOLD"
    if month in GOLD_BEAR_MONTHS: return "HOLD"

    bull_season = month in GOLD_BULL_MONTHS

    # Vol-TSMOM
    ret_n  = (closes[-1]-closes[-lookback])/closes[-lookback]
    ret_7d = (closes[-1]-closes[-7])/closes[-7] if len(closes)>=7 else 0

    vol_threshold = np.percentile(vols[-50:], vol_pct) if len(vols)>=50 else 0
    vol_ok = vols[-1] >= vol_threshold

    score = 0
    # Momentum
    if ret_n > 0.02:  score += 2
    elif ret_n < -0.02: score -= 2
    if ret_7d > 0.01: score += 1
    elif ret_7d < -0.01: score -= 1
    # Volume
    if vol_ok: score += 1
    # Technical
    if ind["ema_trend"] == "BULLISH": score += 2
    elif ind["ema_trend"] == "BEARISH": score -= 2
    if ind["macd_cross"] == "BULLISH": score += 1
    else: score -= 1
    if ind["rsi"] < 40: score += 1
    elif ind["rsi"] > 65: score -= 1
    if ind["bb_pos"] == "OVERSOLD": score += 1
    elif ind["bb_pos"] == "OVERBOUGHT": score -= 1
    # Seasonal bonus
    if bull_season: score += 1

    if score >= 5: return "BUY"
    if score <= -4 and allow_short: return "SELL"
    return "HOLD"

def gold_tsmom_seasonal_adaptive(ind, closes, date, vols,
                                  lookback=30, vol_pct=60, **kw):
    """
    KOMBINASI ADAPTIVE:
    - Bull season + trending → Vol-TSMOM dengan Turtle confirmation
    - Bull season + ranging → Mean reversion dengan seasonal filter
    - Bear season → HOLD total
    """
    if len(closes) < max(lookback+1, 200): return "HOLD"
    month   = pd.Timestamp(date).month
    weekday = pd.Timestamp(date).weekday()

    if weekday == 0: return "HOLD"
    if month in GOLD_BEAR_MONTHS: return "HOLD"

    bull_season = month in GOLD_BULL_MONTHS

    # Regime detection
    s       = pd.Series(closes)
    ret_3m  = (closes[-1]-closes[-63])/closes[-63] if len(closes)>=63 else 0
    vol_20  = float(pd.Series(closes[-20:]).pct_change().std()*np.sqrt(252))
    ema200  = float(s.ewm(span=200).mean().iloc[-1])
    price   = closes[-1]
    is_trending = abs(ret_3m) > 0.06 and vol_20 > 0.10

    # Vol-TSMOM score
    ret_n  = (closes[-1]-closes[-lookback])/closes[-lookback]
    ret_7d = (closes[-1]-closes[-7])/closes[-7] if len(closes)>=7 else 0
    vol_threshold = np.percentile(vols[-50:], vol_pct) if len(vols)>=50 else 0
    vol_ok = vols[-1] >= vol_threshold

    if is_trending:
        # Mode trending: Turtle + Vol-TSMOM confirmation
        score = 0
        if len(closes) >= 21:
            high20 = max(closes[-21:-1])
            if price > high20: score += 3
        if ret_n > 0.03: score += 2
        if ret_7d > 0: score += 1
        if vol_ok: score += 1
        if ind["ema_trend"] == "BULLISH": score += 2
        if ind["macd_cross"] == "BULLISH": score += 1
        if bull_season: score += 1

        if score >= 7 and price > ema200: return "BUY"
        return "HOLD"

    else:
        # Mode ranging: Mean reversion + seasonal + volume
        s50  = pd.Series(closes[-50:])
        ma   = float(s50.rolling(20).mean().iloc[-1])
        std  = float(s50.rolling(20).std().iloc[-1])
        if std == 0: return "HOLD"
        z = (closes[-1]-ma)/std

        score = 0
        if z < -1.8: score += 3
        elif z < -1.2: score += 2
        if ind["rsi"] < 38: score += 2
        elif ind["rsi"] < 45: score += 1
        if ind["stoch_signal"] == "OVERSOLD": score += 1
        if ind["bb_pos"] == "OVERSOLD": score += 1
        if vol_ok: score += 1
        if bull_season: score += 1
        if ret_n > 0: score += 1

        if score >= 6: return "BUY"
        return "HOLD"

def gold_smart_hold(ind, closes, date, vols, **kw):
    """
    Smart Hold: pendekatan minimal trading.
    Hanya entry kalau SEMUA kondisi sangat kuat — mirip B&H tapi dengan
    downside protection dari SL.
    """
    if len(closes) < 200: return "HOLD"
    month   = pd.Timestamp(date).month
    weekday = pd.Timestamp(date).weekday()

    if weekday == 0: return "HOLD"
    if month in GOLD_BEAR_MONTHS: return "HOLD"

    s      = pd.Series(closes)
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    ema50  = float(s.ewm(span=50).mean().iloc[-1])
    price  = closes[-1]
    ret_3m = (closes[-1]-closes[-63])/closes[-63] if len(closes)>=63 else 0

    # Hanya long kalau strong bull conditions
    above_ema200 = price > ema200
    ema_trending = ema50 > ema200
    momentum_ok  = ret_3m > 0.03
    tech_ok      = ind["ema_trend"] == "BULLISH" and ind["macd_cross"] == "BULLISH"

    if above_ema200 and ema_trending and momentum_ok and tech_ok:
        return "BUY"
    return "HOLD"

# ─── Grid Search untuk kombinasi terbaik ─────────────────────────────────────

def grid_search_gold(df, years):
    """Cari parameter lookback & vol_pct terbaik untuk gold_tsmom_seasonal"""
    print(f"\n  🔍 Grid Search parameter (lookback x vol_percentile x SL x TP)...")
    best = {"cagr": -999}
    for lookback in [14, 21, 30, 45, 60]:
        for vol_pct in [40, 50, 60, 70]:
            for sl in [5, 6, 7, 8, 10]:
                for tp in [15, 20, 25, 30]:
                    if tp <= sl: continue
                    try:
                        r = backtest(df, sl, tp,
                                     lambda ind,c,d,v,**kw: gold_tsmom_seasonal(
                                         ind,c,d,v,
                                         lookback=kw.get("lookback",30),
                                         vol_pct=kw.get("vol_pct",60)),
                                     years,
                                     lookback=lookback, vol_pct=vol_pct)
                        if r["cagr"] > best["cagr"]:
                            best = {**r, "lookback":lookback,
                                    "vol_pct":vol_pct, "sl":sl, "tp":tp}
                    except:
                        pass
    return best

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n"+"="*120)
    print("  GOLD FINAL TEST: Vol-TSMOM + Monthly Seasonal Combinations")
    print("="*120)

    periods = [
        ("In-Sample   2015-2020", "2015-01-01","2020-01-01", 5),
        ("Out-of-Sample 2020-2024","2020-01-01","2024-12-31", 4),
        ("Full 2015-2024",        "2015-01-01","2024-12-31",10),
    ]

    strategies = [
        ("Baseline Adaptive",                  lambda i,c,d,v,**kw: __import__('backtest.engine', fromlist=['rule_based_signal']) and None or gold_smart_hold(i,c,d,v)),
        ("Vol-TSMOM only",                     gold_vol_tsmom),
        ("Monthly Seasonal only",              gold_monthly_seasonal),
        ("Kombinasi: TSMOM + Seasonal",        gold_tsmom_seasonal),
        ("Kombinasi Adaptive (best effort)",   gold_tsmom_seasonal_adaptive),
        ("Smart Hold",                         gold_smart_hold),
    ]

    # Fix baseline
    def gold_baseline_fn(ind, closes, date, vols, **kw):
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
                if price > high20 and ind["ema_trend"] == "BULLISH": return "BUY"
        else:
            s50 = pd.Series(closes[-50:])
            ma  = float(s50.rolling(20).mean().iloc[-1])
            std = float(s50.rolling(20).std().iloc[-1])
            if std > 0:
                z = (closes[-1]-ma)/std
                if z < -2.2 and ind["rsi"] < 40 and ind["bb_pos"] == "OVERSOLD":
                    return "BUY"
        return "HOLD"

    strategies = [
        ("Baseline Adaptive",                  gold_baseline_fn),
        ("Vol-TSMOM only",                     gold_vol_tsmom),
        ("Monthly Seasonal only",              gold_monthly_seasonal),
        ("Kombinasi: TSMOM + Seasonal",        gold_tsmom_seasonal),
        ("Kombinasi Adaptive",                 gold_tsmom_seasonal_adaptive),
        ("Smart Hold",                         gold_smart_hold),
    ]

    all_results = {}
    for period, start, end, years in periods:
        print(f"\n  📅 {period}")
        print(f"  {'─'*117}")
        df = load_data("stock", "GC=F", start, end, timeframe="1d")
        if df is None or len(df) < 300:
            print("  ❌ Data tidak cukup"); continue

        bh_r = bh_metrics(df, years)
        print(f"  {'B&H 3x (target)':<45} | CAGR:{bh_r['cagr']:6.1f}%   "
              f"| DD:{bh_r['dd']:6.1f}% | Sharpe:{bh_r['sharpe']:5.2f}")
        print(f"  {'─'*117}")

        period_res = {}
        for label, fn in strategies:
            r = backtest(df, 8.0, 30.0, fn, years)
            period_res[label] = r
            prow(label, r, bh_r["cagr"])
        all_results[period] = (period_res, bh_r["cagr"])

    # Grid search di full period
    print(f"\n{'='*120}")
    print(f"  GRID SEARCH — Cari parameter optimal untuk TSMOM + Seasonal")
    print(f"{'='*120}")
    df_full = load_data("stock", "GC=F", "2015-01-01", "2024-12-31", timeframe="1d")

    # In-sample grid search
    df_is = load_data("stock", "GC=F", "2015-01-01", "2020-01-01", timeframe="1d")
    best_is = grid_search_gold(df_is, 5)
    print(f"\n  🏆 Best In-Sample params: "
          f"lookback={best_is.get('lookback')} | "
          f"vol_pct={best_is.get('vol_pct')} | "
          f"SL={best_is.get('sl')}% | TP={best_is.get('tp')}%")
    print(f"     In-Sample  CAGR: {best_is.get('cagr'):.1f}% | "
          f"DD: {best_is.get('dd'):.1f}% | "
          f"Sharpe: {best_is.get('sharpe'):.2f}")

    # Validasi di out-of-sample
    df_oos = load_data("stock", "GC=F", "2020-01-01", "2024-12-31", timeframe="1d")
    bh_oos = bh_metrics(df_oos, 4)

    lb   = best_is.get("lookback", 30)
    vpct = best_is.get("vol_pct", 60)
    sl_g = best_is.get("sl", 8)
    tp_g = best_is.get("tp", 30)

    r_oos = backtest(df_oos, sl_g, tp_g,
                     lambda ind,c,d,v,**kw: gold_tsmom_seasonal(
                         ind,c,d,v,lookback=lb,vol_pct=vpct), 4)
    beat_oos = "✅ BEAT" if r_oos["cagr"] > bh_oos["cagr"] else "❌ Belum beat"
    print(f"     Out-of-Sample CAGR: {r_oos['cagr']:.1f}% vs B&H {bh_oos['cagr']:.1f}% | {beat_oos}")
    print(f"     DD: {r_oos['dd']:.1f}% | Sharpe: {r_oos['sharpe']:.2f} | WR: {r_oos['wr']:.1f}% | T:{r_oos['trades']}")

    # Scoring konsistensi
    print(f"\n  📊 CONSISTENCY SCORE:")
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
            if r["dd"] > -50:       score += 1
        scores[label] = score

    for label, sc in sorted(scores.items(), key=lambda x:-x[1]):
        bar = "█"*sc + "░"*(14-min(sc,14))
        print(f"     {label:<45} | Score:{sc:2d}/14 | {bar}")

    best = max(scores, key=scores.get)
    bh_full = bh_metrics(df_full, 10)
    best_full = all_results.get("Full 2015-2024",({},0))[0].get(best,{})
    beat_bh = "✅ BEAT B&H!" if best_full.get("cagr",0) > bh_full["cagr"] else "❌ Belum beat B&H"

    print(f"\n  🏆 PALING KONSISTEN: {best} (Score:{scores[best]}/14)")
    print(f"  Full CAGR: {best_full.get('cagr',0):.1f}% vs B&H {bh_full['cagr']:.1f}% | {beat_bh}")
    print(f"\n  💡 KESIMPULAN:")
    if best_full.get("cagr",0) > bh_full["cagr"]:
        print(f"  ✅ Strategi '{best}' berhasil beat B&H Gold!")
        print(f"  Implementasikan ke bot dengan: SL={sl_g}% TP={tp_g}% lookback={lb} vol_pct={vpct}")
    else:
        print(f"  ❌ Tidak ada kombinasi yang beat B&H Gold secara konsisten.")
        print(f"  Rekomendasi: Gunakan Smart Hold untuk Gold (minimal trade, maksimal protection)")
        print(f"  Smart Hold Full CAGR: {all_results.get('Full 2015-2024',({},0))[0].get('Smart Hold',{}).get('cagr',0):.1f}%")