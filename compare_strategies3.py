# compare_strategies3.py
# Test: Volume filter, Strong confirmation, Asset substitution, + Hedge Fund strategies

import sys, os
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np
from backtest.data_loader import load_data
from core.indicators import calc_indicators

INITIAL      = 1000.0
RISK_FREE    = 0.05
LEVERAGE     = 3
YEARS_FULL   = 10
START        = "2015-01-01"
END          = "2024-12-31"

# ─── Metrics ─────────────────────────────────────────────────────────────────

def cagr(initial, final, years):
    if final <= 0 or initial <= 0: return -99.9
    return round(((final/initial)**(1/years)-1)*100, 1)

def sharpe(equity, years, rfr=RISK_FREE):
    eq = np.array(equity)
    if len(eq) < 2: return 0.0
    dr = np.diff(eq)/eq[:-1]
    if dr.std() == 0: return 0.0
    ar = (eq[-1]/eq[0])**(1/years)-1
    return round((ar-rfr)/(dr.std()*np.sqrt(252)), 2)

def sortino(equity, years, rfr=RISK_FREE):
    eq = np.array(equity)
    if len(eq) < 2: return 0.0
    dr = np.diff(eq)/eq[:-1]
    dv = dr[dr<0].std()
    if dv == 0: return 0.0
    ar = (eq[-1]/eq[0])**(1/years)-1
    return round((ar-rfr)/(dv*np.sqrt(252)), 2)

def max_dd(equity):
    eq   = np.array(equity)
    peak = np.maximum.accumulate(eq)
    return round(float(((eq-peak)/peak*100).min()), 1)

def calmar(c, dd):
    return round(c/abs(dd), 3) if dd != 0 else 0.0

def winrate(trades):
    if not trades: return 0.0
    return round(sum(1 for t in trades if t["pnl"]>0)/len(trades)*100, 1)

def metrics(equity, trades, years):
    eq   = np.array(equity)
    final = eq[-1]
    c    = cagr(INITIAL, final, years)
    dd   = max_dd(equity)
    return {
        "cagr":    c,
        "final":   round(final, 2),
        "dd":      dd,
        "sharpe":  sharpe(equity, years),
        "sortino": sortino(equity, years),
        "calmar":  calmar(c, dd),
        "wr":      winrate(trades),
        "trades":  len(trades),
    }

def print_row(label, r, bh_cagr, w=35):
    beat  = "✅" if r["cagr"] > bh_cagr else "❌"
    sg    = "🟢" if r["sharpe"]>1.5 else ("🟡" if r["sharpe"]>0.8 else "🔴")
    print(f"  {label:<{w}} | CAGR:{r['cagr']:6.1f}%{beat}"
          f" | DD:{r['dd']:6.1f}%"
          f" | Sharpe:{r['sharpe']:5.2f}{sg}"
          f" | Sortino:{r['sortino']:5.2f}"
          f" | Calmar:{r['calmar']:5.3f}"
          f" | WR:{r['wr']:5.1f}% | T:{r['trades']}")

# ─── Signal Library ───────────────────────────────────────────────────────────

def sig_momentum(ind, closes=None, allow_short=True):
    score = 0
    if ind["ema_trend"] == "BULLISH": score += 3
    elif ind["ema_trend"] == "BEARISH": score -= 3
    if ind["macd_cross"] == "BULLISH": score += 2
    else: score -= 2
    if ind["rsi"] < 30: score += 1
    elif ind["rsi"] > 70: score -= 1
    if score >= 3: return "BUY"
    if score <= -3 and allow_short: return "SELL"
    return "HOLD"

def sig_strong_confirm(ind, closes=None, allow_short=True):
    """Opsi B: Hanya entry kalau 4+ indikator sepakat kuat"""
    votes_buy  = 0
    votes_sell = 0

    # RSI
    if ind["rsi"] < 30: votes_buy  += 1
    elif ind["rsi"] > 70: votes_sell += 1

    # MACD
    if ind["macd_cross"] == "BULLISH": votes_buy  += 1
    elif ind["macd_cross"] == "BEARISH": votes_sell += 1

    # EMA trend
    if ind["ema_trend"] == "BULLISH": votes_buy  += 1
    elif ind["ema_trend"] == "BEARISH": votes_sell += 1

    # BB
    if ind["bb_pos"] == "OVERSOLD":    votes_buy  += 1
    elif ind["bb_pos"] == "OVERBOUGHT": votes_sell += 1

    # Stoch
    if ind["stoch_signal"] == "OVERSOLD":    votes_buy  += 1
    elif ind["stoch_signal"] == "OVERBOUGHT": votes_sell += 1

    if votes_buy  >= 4: return "BUY"
    if votes_sell >= 4 and allow_short: return "SELL"
    return "HOLD"

def sig_turtle(ind, closes, allow_short=True):
    """Opsi D (Hedge Fund): Turtle Trading — Donchian Channel Breakout
       Strategi trend-following klasik dipakai banyak hedge fund besar.
       Entry kalau harga breakout 20-day high/low."""
    if len(closes) < 20: return "HOLD"
    high20 = max(closes[-20:])
    low20  = min(closes[-20:])
    price  = closes[-1]
    if price >= high20: return "BUY"
    if price <= low20 and allow_short: return "SELL"
    return "HOLD"

def sig_mean_reversion(ind, closes, allow_short=True):
    """Opsi D (Hedge Fund): Mean Reversion + Bollinger Bands
       Strategi statistik arb yang dipakai quant funds."""
    if len(closes) < 20: return "HOLD"
    s     = pd.Series(closes)
    ma    = s.rolling(20).mean().iloc[-1]
    std   = s.rolling(20).std().iloc[-1]
    price = closes[-1]
    z_score = (price - ma) / std if std > 0 else 0

    if z_score < -2.0: return "BUY"   # harga sangat jauh di bawah mean
    if z_score > 2.0 and allow_short: return "SELL"
    return "HOLD"

def sig_dual_momentum(ind, closes, allow_short=True):
    """Opsi D (Hedge Fund): Dual Momentum (Gary Antonacci)
       Absolute + Relative momentum. Salah satu strategi hedge fund paling direplikasi."""
    if len(closes) < 252: return "HOLD"
    ret_12m = (closes[-1] - closes[-252]) / closes[-252]  # 12-month return
    ret_1m  = (closes[-1] - closes[-21])  / closes[-21]   # 1-month return

    # Absolute momentum: return 12 bulan harus positif untuk long
    # Relative momentum: return 1 bulan menentukan arah
    if ret_12m > 0 and ret_1m > 0: return "BUY"
    if ret_12m < 0 and allow_short: return "SELL"
    return "HOLD"

def sig_combined_hf(ind, closes, allow_short=True):
    """Opsi D (Hedge Fund): Kombinasi Turtle + Dual Momentum + EMA filter
       Hanya entry kalau semua 3 metode setuju = conviction tinggi"""
    if len(closes) < 252: return "HOLD"

    turtle  = sig_turtle(ind, closes, allow_short)
    dualm   = sig_dual_momentum(ind, closes, allow_short)
    ema_ok  = ind["ema_trend"] == "BULLISH"

    # BUY hanya kalau turtle BUY + dual momentum BUY + EMA bullish
    if turtle == "BUY" and dualm == "BUY" and ema_ok:
        return "BUY"
    # SELL hanya kalau turtle SELL + dual momentum SELL
    if turtle == "SELL" and dualm == "SELL" and allow_short:
        return "SELL"
    return "HOLD"

# ─── Backtest Engine ──────────────────────────────────────────────────────────

def run(df, sl, tp, leverage, sig_fn, years, **sig_kwargs):
    closes  = df["close"].tolist()
    balance = INITIAL
    pos     = None
    trades  = []
    equity  = [INITIAL]

    for i in range(252, len(closes)):
        price = closes[i]
        ind   = calc_indicators(closes[:i+1])
        if ind is None: continue

        sig = sig_fn(ind, closes[:i+1], **sig_kwargs)

        # SL/TP
        if pos:
            pnl_pct = ((price-pos["entry"])/pos["entry"]*100*leverage
                       if pos["type"]=="long" else
                       (pos["entry"]-price)/pos["entry"]*100*leverage)
            if pnl_pct <= -sl or pnl_pct >= tp:
                pnl = ((price-pos["entry"])*pos["qty"] if pos["type"]=="long"
                       else (pos["entry"]-price)*pos["qty"])
                balance += pos["amount"] + pnl
                trades.append({"pnl": pnl})
                pos = None
                equity.append(balance)
                continue

        if not pos:
            if sig == "BUY":
                pos = {"type":"long","entry":price,
                       "qty":(balance*leverage)/price,"amount":balance}
                balance = 0
            elif sig == "SELL":
                pos = {"type":"short","entry":price,
                       "qty":(balance*leverage)/price,"amount":balance}
                balance = 0

    if pos:
        price = closes[-1]
        pnl   = ((price-pos["entry"])*pos["qty"] if pos["type"]=="long"
                 else (pos["entry"]-price)*pos["qty"])
        balance += pos["amount"] + pnl
        trades.append({"pnl": pnl})
        equity.append(balance)

    return metrics(equity, trades, years)

# ─── Volume filter wrapper ────────────────────────────────────────────────────

def run_volume_filter(df, sl, tp, leverage, sig_fn, years, vol_percentile=60, **sig_kwargs):
    """Opsi A: Hanya trade kalau volume > percentile ke-N"""
    closes  = df["close"].tolist()
    volumes = df["volume"].tolist() if "volume" in df.columns else [1]*len(df)
    balance = INITIAL
    pos     = None
    trades  = []
    equity  = [INITIAL]

    for i in range(252, len(closes)):
        price = closes[i]
        ind   = calc_indicators(closes[:i+1])
        if ind is None: continue

        # Volume filter
        recent_vols = volumes[max(0,i-50):i]
        vol_threshold = np.percentile(recent_vols, vol_percentile) if recent_vols else 0
        high_volume = volumes[i] >= vol_threshold

        sig = sig_fn(ind, closes[:i+1], **sig_kwargs)

        # Hanya eksekusi sinyal kalau volume tinggi
        if not high_volume and sig in ("BUY","SELL"):
            sig = "HOLD"

        if pos:
            pnl_pct = ((price-pos["entry"])/pos["entry"]*100*leverage
                       if pos["type"]=="long" else
                       (pos["entry"]-price)/pos["entry"]*100*leverage)
            if pnl_pct <= -sl or pnl_pct >= tp:
                pnl = ((price-pos["entry"])*pos["qty"] if pos["type"]=="long"
                       else (pos["entry"]-price)*pos["qty"])
                balance += pos["amount"] + pnl
                trades.append({"pnl": pnl})
                pos = None
                equity.append(balance)
                continue

        if not pos:
            if sig == "BUY":
                pos = {"type":"long","entry":price,
                       "qty":(balance*leverage)/price,"amount":balance}
                balance = 0
            elif sig == "SELL":
                pos = {"type":"short","entry":price,
                       "qty":(balance*leverage)/price,"amount":balance}
                balance = 0

    if pos:
        price = closes[-1]
        pnl   = ((price-pos["entry"])*pos["qty"] if pos["type"]=="long"
                 else (pos["entry"]-price)*pos["qty"])
        balance += pos["amount"] + pnl
        trades.append({"pnl": pnl})
        equity.append(balance)

    return metrics(equity, trades, years)

# ─── BH Benchmark ────────────────────────────────────────────────────────────

def bh(df, leverage, years):
    s = df["close"].iloc[0]
    eq = [max(INITIAL*(1+(p-s)/s*leverage), 0.01) for p in df["close"]]
    c = cagr(INITIAL, eq[-1], years)
    return {"cagr":c, "dd":max_dd(eq), "sharpe":sharpe(eq,years),
            "sortino":sortino(eq,years), "calmar":calmar(c,max_dd(eq))}

# ─── Main ─────────────────────────────────────────────────────────────────────

def test_asset(name, symbol, asset_type, sl, tp, allow_short=True):
    print(f"\n{'='*115}")
    print(f"  {name} ({symbol})")
    print(f"{'='*115}")

    # Load semua periode
    data = {}
    for label, s, e, y in [
        ("in_sample",  "2015-01-01","2020-01-01", 5),
        ("out_sample", "2020-01-01","2024-12-31", 4),
        ("full",       "2015-01-01","2024-12-31",10),
    ]:
        df = load_data(asset_type, symbol, s, e, timeframe="1d")
        data[label] = (df, y)

    all_results = {}

    for period_label, (df, years) in data.items():
        if df is None or len(df) < 300:
            print(f"  ❌ {period_label}: data tidak cukup"); continue

        label_map = {"in_sample":"📅 In-Sample 2015-2020",
                     "out_sample":"📅 Out-of-Sample 2020-2024",
                     "full":"📅 Full 2015-2024"}
        print(f"\n  {label_map[period_label]}")
        print(f"  {'─'*112}")

        bh_r = bh(df, LEVERAGE, years)
        print(f"  {'B&H 3x':<35} | CAGR:{bh_r['cagr']:6.1f}%   "
              f"| DD:{bh_r['dd']:6.1f}% | Sharpe:{bh_r['sharpe']:5.2f}    "
              f"| Sortino:{bh_r['sortino']:5.2f} | Calmar:{bh_r['calmar']:5.3f}")
        print(f"  {'─'*112}")

        period_results = {}

        # A: Momentum + Volume Filter
        r = run_volume_filter(df, sl, tp, LEVERAGE, sig_momentum, years,
                              allow_short=allow_short)
        period_results["A_Volume+Momentum"] = r
        print_row("A. Momentum + Volume Filter", r, bh_r["cagr"])

        # B: Strong Confirmation (4+ indikator)
        r = run(df, sl, tp, LEVERAGE,
                lambda ind, cl, **kw: sig_strong_confirm(ind, kw.get("allow_short",True)),
                years, allow_short=allow_short)
        period_results["B_StrongConfirm"] = r
        print_row("B. Strong Confirm (4+ votes)", r, bh_r["cagr"])

        # D1: Turtle Breakout
        r = run(df, sl, tp, LEVERAGE,
                lambda ind, cl, **kw: sig_turtle(ind, cl, kw.get("allow_short",True)),
                years, allow_short=allow_short)
        period_results["D1_Turtle"] = r
        print_row("D1. Hedge Fund: Turtle Breakout", r, bh_r["cagr"])

        # D2: Mean Reversion
        r = run(df, sl, tp, LEVERAGE,
                lambda ind, cl, **kw: sig_mean_reversion(ind, cl, kw.get("allow_short",True)),
                years, allow_short=allow_short)
        period_results["D2_MeanReversion"] = r
        print_row("D2. Hedge Fund: Mean Reversion", r, bh_r["cagr"])

        # D3: Dual Momentum
        r = run(df, sl, tp, LEVERAGE,
                lambda ind, cl, **kw: sig_dual_momentum(ind, cl, kw.get("allow_short",True)),
                years, allow_short=allow_short)
        period_results["D3_DualMomentum"] = r
        print_row("D3. Hedge Fund: Dual Momentum", r, bh_r["cagr"])

        # D4: Combined HF (Turtle + Dual Momentum + EMA)
        r = run(df, sl, tp, LEVERAGE,
                lambda ind, cl, **kw: sig_combined_hf(ind, cl, kw.get("allow_short",True)),
                years, allow_short=allow_short)
        period_results["D4_CombinedHF"] = r
        print_row("D4. Hedge Fund: Combined HF", r, bh_r["cagr"])

        # Simpan hasil
        all_results[period_label] = (period_results, bh_r["cagr"])

    # Scoring lintas periode — strategi terbaik adalah yang konsisten
    print(f"\n  {'─'*112}")
    print(f"  📊 SCORING KONSISTENSI (in-sample + out-of-sample):")
    scores = {}
    for strat in ["A_Volume+Momentum","B_StrongConfirm",
                  "D1_Turtle","D2_MeanReversion","D3_DualMomentum","D4_CombinedHF"]:
        score = 0
        for period_label in ["in_sample","out_sample"]:
            if period_label not in all_results: continue
            period_results, bh_cagr_val = all_results[period_label]
            if strat not in period_results: continue
            r = period_results[strat]
            if r["cagr"] > bh_cagr_val: score += 3
            if r["sharpe"] > 0.8:       score += 2
            if r["calmar"] > 0.5:       score += 1
            if r["dd"] > -50:           score += 1  # DD tidak terlalu dalam
        scores[strat] = score

    for strat, sc in sorted(scores.items(), key=lambda x: -x[1]):
        bar = "█" * sc + "░" * (14-min(sc,14))
        print(f"     {strat:<30} | Score:{sc:2d}/14 | {bar}")

    best = max(scores, key=scores.get)
    print(f"\n  🏆 PALING KONSISTEN: {best} (Score: {scores[best]}/14)")

    return scores, best

if __name__ == "__main__":
    print("\n" + "="*115)
    print("  COMPREHENSIVE STRATEGY TEST + HEDGE FUND STRATEGIES")
    print(f"  Periode: {START} → {END} | Leverage: {LEVERAGE}x")
    print("  Strategi HF: Turtle Breakout | Mean Reversion | Dual Momentum | Combined")
    print("="*115)

    assets = [
        ("Bitcoin",  "BTC/USDT", "crypto", 6.0,  30.0, False),
        ("Gold",     "GC=F",     "stock",  8.0,  30.0, True),
        ("S&P 500",  "^GSPC",    "stock",  10.0, 30.0, False),
    ]

    final_summary = []
    for name, sym, atype, sl, tp, ashort in assets:
        scores, best = test_asset(name, sym, atype, sl, tp, ashort)
        final_summary.append({"aset":name, "best":best, "score":scores[best]})

    print("\n" + "="*115)
    print("  REKOMENDASI FINAL PER ASET")
    print("="*115)
    for s in final_summary:
        print(f"  {s['aset']:10} → Gunakan: {s['best']} (Consistency Score: {s['score']}/14)")

    print("""
  ─────────────────────────────────────────────────────────────────
  📖 PENJELASAN STRATEGI HEDGE FUND:

  D1. Turtle Breakout  → Richard Dennis/William Eckhardt. Entry saat harga
      breakout 20-day high/low. Trend-following klasik.

  D2. Mean Reversion   → Statistik arb. Jual saat harga 2σ di atas mean,
      beli saat 2σ di bawah. Efektif di aset ranging.

  D3. Dual Momentum    → Gary Antonacci. Kombinasi absolute momentum (12-bulan)
      + relative momentum (1-bulan). Salah satu faktor risk premium terbukti.

  D4. Combined HF      → Turtle + Dual Momentum + EMA filter. Entry hanya
      kalau semua 3 metode setuju = conviction tinggi, trade lebih sedikit.
  ─────────────────────────────────────────────────────────────────
    """)