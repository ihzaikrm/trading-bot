# compare_strategies.py
# Test 4 strategi improvement dan bandingkan CAGR vs Buy & Hold

import sys, os
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np
from backtest.data_loader import load_data
from core.indicators import calc_indicators

START = "2015-01-01"
END   = "2024-12-31"
YEARS = 10
LEVERAGE = 3
INITIAL  = 1000.0

# ── Helpers ──────────────────────────────────────────────────────────────────

def cagr(initial, final, years):
    if final <= 0 or initial <= 0: return -99.9
    return ((final / initial) ** (1 / years) - 1) * 100

def max_drawdown(equity_curve):
    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak * 100
    return round(float(dd.min()), 2)

def winrate(trades):
    if not trades: return 0.0
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return round(wins / len(trades) * 100, 1)

def buy_and_hold_cagr(df, leverage=1, years=YEARS):
    start_price = df["close"].iloc[0]
    end_price   = df["close"].iloc[-1]
    raw_return  = (end_price - start_price) / start_price
    # Leverage sederhana (tidak ada SL/TP untuk buy & hold)
    leveraged   = raw_return * leverage
    final       = INITIAL * (1 + leveraged)
    return cagr(INITIAL, final, years), round(leveraged * 100, 1)

# ── Signal Functions ──────────────────────────────────────────────────────────

def rule_based_signal(ind, allow_short=True):
    score = 0
    if ind["rsi"] < 35: score += 2
    elif ind["rsi"] > 65: score -= 2
    if ind["macd_cross"] == "BULLISH": score += 1
    else: score -= 1
    if ind["ema_trend"] == "BULLISH": score += 1
    elif ind["ema_trend"] == "BEARISH": score -= 1
    if ind["bb_pos"] == "OVERSOLD": score += 1
    elif ind["bb_pos"] == "OVERBOUGHT": score -= 1
    if ind["stoch_signal"] == "OVERSOLD": score += 1
    elif ind["stoch_signal"] == "OVERBOUGHT": score -= 1

    if score >= 3: return "BUY"
    if score <= -3 and allow_short: return "SELL"
    return "HOLD"

def weekly_bias(closes_weekly):
    """Hitung bias dari data mingguan"""
    ind = calc_indicators(closes_weekly)
    if ind is None: return "NEUTRAL"
    score = 0
    if ind["ema_trend"] == "BULLISH": score += 2
    elif ind["ema_trend"] == "BEARISH": score -= 2
    if ind["macd_cross"] == "BULLISH": score += 1
    else: score -= 1
    if ind["rsi"] > 55: score += 1
    elif ind["rsi"] < 45: score -= 1
    if score >= 2: return "BULL"
    if score <= -2: return "BEAR"
    return "NEUTRAL"

def regime(closes_200):
    """Deteksi regime pasar berdasarkan EMA200"""
    if len(closes_200) < 200: return "UNKNOWN"
    s = pd.Series(closes_200)
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes_200[-1]
    ema50  = float(s.ewm(span=50).mean().iloc[-1])
    if price > ema200 and ema50 > ema200: return "BULL"
    if price < ema200 and ema50 < ema200: return "BEAR"
    return "SIDEWAYS"

# ── Core Backtest Runner ──────────────────────────────────────────────────────

def run_backtest(df, sl_pct, tp_pct, leverage,
                 allow_short=True,
                 use_weekly_filter=False,
                 use_regime=False,
                 df_weekly=None):

    closes = df["close"].tolist()
    closes_w = df_weekly["close"].tolist() if df_weekly is not None else []

    balance  = INITIAL
    position = None
    trades   = []
    equity   = [INITIAL]

    for i in range(200, len(closes)):
        price = closes[i]
        ind   = calc_indicators(closes[:i+1])
        if ind is None:
            continue

        # ── Weekly bias filter ──
        w_bias = "NEUTRAL"
        if use_weekly_filter and df_weekly is not None:
            # Cari index minggu yang sesuai dengan hari ini
            day_date = df.index[i]
            w_closes = [c for c, d in zip(closes_w, df_weekly.index) if d <= day_date]
            if len(w_closes) >= 50:
                w_bias = weekly_bias(w_closes)

        # ── Regime detection ──
        mkt_regime = "UNKNOWN"
        if use_regime:
            mkt_regime = regime(closes[:i+1])

        # ── Signal ──
        # Kalau weekly BEAR → jangan buka long baru
        # Kalau weekly BULL → jangan buka short baru
        _allow_short = allow_short
        if use_weekly_filter:
            if w_bias == "BULL":  _allow_short = False
            if w_bias == "BEAR":  pass  # boleh short

        if use_regime:
            if mkt_regime == "BULL": _allow_short = False
            if mkt_regime == "BEAR": pass

        signal = rule_based_signal(ind, allow_short=_allow_short)

        # ── Cek SL/TP ──
        if position:
            if position["type"] == "long":
                pnl_pct = (price - position["entry"]) / position["entry"] * 100 * leverage
            else:
                pnl_pct = (position["entry"] - price) / position["entry"] * 100 * leverage

            if pnl_pct <= -sl_pct or pnl_pct >= tp_pct:
                if position["type"] == "long":
                    pnl = (price - position["entry"]) * position["qty"]
                else:
                    pnl = (position["entry"] - price) * position["qty"]
                balance += position["amount"] + pnl
                trades.append({"pnl": pnl, "type": position["type"], "reason": "SL/TP"})
                position = None
                equity.append(balance)
                continue

        # ── Entry ──
        if not position:
            if signal == "BUY":
                qty = (balance * leverage) / price
                position = {"type": "long",  "entry": price, "qty": qty, "amount": balance}
                balance  = 0
            elif signal == "SELL" and _allow_short:
                qty = (balance * leverage) / price
                position = {"type": "short", "entry": price, "qty": qty, "amount": balance}
                balance  = 0

    # ── Tutup posisi di akhir ──
    if position:
        price = closes[-1]
        if position["type"] == "long":
            pnl = (price - position["entry"]) * position["qty"]
        else:
            pnl = (position["entry"] - price) * position["qty"]
        balance += position["amount"] + pnl
        trades.append({"pnl": pnl, "type": position["type"], "reason": "End"})
        equity.append(balance)

    return {
        "final":    round(balance, 2),
        "cagr":     round(cagr(INITIAL, balance, YEARS), 1),
        "total_ret":round((balance - INITIAL) / INITIAL * 100, 1),
        "winrate":  winrate(trades),
        "trades":   len(trades),
        "max_dd":   max_drawdown(equity),
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def test_asset(name, symbol, asset_type, sl, tp, asymmetric_sl=None, asymmetric_tp=None):
    print(f"\n{'='*60}")
    print(f"  ASET: {name} ({symbol})")
    print(f"{'='*60}")

    # Load data harian
    df = load_data(asset_type, symbol, START, END, timeframe="1d")
    if df is None or len(df) < 300:
        print("  ❌ Data tidak cukup"); return

    # Load data mingguan
    df_w = load_data(asset_type, symbol, START, END, timeframe="1wk")

    # Buy & Hold
    bh_cagr, bh_ret = buy_and_hold_cagr(df, leverage=LEVERAGE)
    print(f"\n  📌 BUY & HOLD (3x leverage): CAGR={bh_cagr:.1f}% | Return={bh_ret:.1f}%")
    print(f"  {'─'*55}")

    results = {}

    # ── BASELINE ──
    r = run_backtest(df, sl, tp, LEVERAGE, allow_short=True)
    results["Baseline"] = r
    print(f"  Baseline          | CAGR:{r['cagr']:6.1f}% | DD:{r['max_dd']:6.1f}% | WR:{r['winrate']:5.1f}% | Trades:{r['trades']}")

    # ── TEST 1: Long Only ──
    r = run_backtest(df, sl, tp, LEVERAGE, allow_short=False)
    results["LongOnly"] = r
    print(f"  Test1 Long-Only   | CAGR:{r['cagr']:6.1f}% | DD:{r['max_dd']:6.1f}% | WR:{r['winrate']:5.1f}% | Trades:{r['trades']}")

    # ── TEST 2: Weekly Filter ──
    r = run_backtest(df, sl, tp, LEVERAGE, allow_short=True,
                     use_weekly_filter=True, df_weekly=df_w)
    results["WeeklyFilter"] = r
    print(f"  Test2 WeeklyBias  | CAGR:{r['cagr']:6.1f}% | DD:{r['max_dd']:6.1f}% | WR:{r['winrate']:5.1f}% | Trades:{r['trades']}")

    # ── TEST 3: Asymmetric SL/TP ──
    _sl = asymmetric_sl or sl * 1.5
    _tp = asymmetric_tp or tp * 2.5
    r = run_backtest(df, _sl, _tp, LEVERAGE, allow_short=True)
    results["AsymSLTP"] = r
    print(f"  Test3 Asym SL/TP  | CAGR:{r['cagr']:6.1f}% | DD:{r['max_dd']:6.1f}% | WR:{r['winrate']:5.1f}% | Trades:{r['trades']} (SL:{_sl}% TP:{_tp}%)")

    # ── TEST 4: Regime Detection ──
    r = run_backtest(df, sl, tp, LEVERAGE, allow_short=True, use_regime=True)
    results["Regime"] = r
    print(f"  Test4 Regime      | CAGR:{r['cagr']:6.1f}% | DD:{r['max_dd']:6.1f}% | WR:{r['winrate']:5.1f}% | Trades:{r['trades']}")

    # ── TEST 5: Kombinasi Terbaik ──
    r = run_backtest(df, _sl, _tp, LEVERAGE,
                     allow_short=False if "BTC" in name else True,
                     use_weekly_filter=True,
                     use_regime=True,
                     df_weekly=df_w)
    results["Kombinasi"] = r
    print(f"  Test5 Kombinasi   | CAGR:{r['cagr']:6.1f}% | DD:{r['max_dd']:6.1f}% | WR:{r['winrate']:5.1f}% | Trades:{r['trades']}")

    # ── Winner ──
    best_name = max(results, key=lambda k: results[k]["cagr"])
    best_cagr = results[best_name]["cagr"]
    beat = "✅ BEAT" if best_cagr > bh_cagr else "❌ BELUM BEAT"
    print(f"\n  🏆 TERBAIK: {best_name} → CAGR {best_cagr:.1f}% {beat} Buy&Hold ({bh_cagr:.1f}%)")

    return results, bh_cagr

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  STRATEGY COMPARISON - BEAT BUY & HOLD")
    print(f"  Periode: {START} → {END} | Leverage: {LEVERAGE}x")
    print("="*60)

    assets = [
        ("Bitcoin",  "BTC/USDT", "crypto", 5.0, 10.0, 8.0, 25.0),
        ("Gold",     "GC=F",     "stock",  5.0, 10.0, 7.0, 20.0),
        ("S&P 500",  "^GSPC",    "stock",  4.0,  5.0, 6.0, 12.0),
    ]

    summary = []
    for name, sym, atype, sl, tp, asl, atp in assets:
        res = test_asset(name, sym, atype, sl, tp, asl, atp)
        if res:
            results, bh = res
            best = max(results, key=lambda k: results[k]["cagr"])
            summary.append({
                "aset": name,
                "bh_cagr": bh,
                "best_strat": best,
                "best_cagr": results[best]["cagr"],
                "beat": results[best]["cagr"] > bh
            })

    print("\n" + "="*60)
    print("  RINGKASAN FINAL")
    print("="*60)
    for s in summary:
        status = "✅ BEAT" if s["beat"] else "❌ BELUM"
        print(f"  {s['aset']:10} | B&H: {s['bh_cagr']:5.1f}% | Best: {s['best_strat']:15} → {s['best_cagr']:5.1f}% | {status}")