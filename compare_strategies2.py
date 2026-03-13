# compare_strategies2.py
# Test lanjutan: Momentum, Higher Leverage, SL/TP Grid, fokus Gold & SPX

import sys, os
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np
from backtest.data_loader import load_data
from core.indicators import calc_indicators

START = "2015-01-01"
END   = "2024-12-31"
YEARS = 10
INITIAL = 1000.0

# ── Helpers ──────────────────────────────────────────────────────────────────

def cagr(initial, final, years=YEARS):
    if final <= 0 or initial <= 0: return -99.9
    return round(((final / initial) ** (1 / years) - 1) * 100, 1)

def max_drawdown(equity_curve):
    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak * 100
    return round(float(dd.min()), 1)

def winrate(trades):
    if not trades: return 0.0
    return round(sum(1 for t in trades if t["pnl"] > 0) / len(trades) * 100, 1)

def bh_cagr(df, leverage):
    start = df["close"].iloc[0]
    end   = df["close"].iloc[-1]
    ret   = (end - start) / start * leverage
    return cagr(INITIAL, INITIAL * (1 + ret)), round(ret * 100, 1)

# ── Signals ──────────────────────────────────────────────────────────────────

def signal_standard(ind, allow_short=True):
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

def signal_momentum(ind, closes, allow_short=True):
    """
    Momentum: ikuti trend selama masih kuat.
    Entry lebih mudah, exit hanya kalau trend berbalik.
    """
    score = 0
    # EMA trend adalah penentu utama
    if ind["ema_trend"] == "BULLISH": score += 3
    elif ind["ema_trend"] == "BEARISH": score -= 3
    # MACD konfirmasi
    if ind["macd_cross"] == "BULLISH": score += 2
    else: score -= 2
    # RSI - hanya extreme yang dihitung
    if ind["rsi"] < 30: score += 1
    elif ind["rsi"] > 70: score -= 1

    if score >= 3: return "BUY"
    if score <= -3 and allow_short: return "SELL"
    return "HOLD"

# ── Backtest Engine ───────────────────────────────────────────────────────────

def run(df, sl, tp, leverage, allow_short=True, use_momentum=False):
    closes  = df["close"].tolist()
    balance = INITIAL
    pos     = None
    trades  = []
    equity  = [INITIAL]

    for i in range(200, len(closes)):
        price = closes[i]
        ind   = calc_indicators(closes[:i+1])
        if ind is None: continue

        sig = (signal_momentum(ind, closes[:i+1], allow_short)
               if use_momentum else
               signal_standard(ind, allow_short))

        # SL/TP check
        if pos:
            pnl_pct = ((price - pos["entry"]) / pos["entry"] * 100 * leverage
                       if pos["type"] == "long" else
                       (pos["entry"] - price) / pos["entry"] * 100 * leverage)
            if pnl_pct <= -sl or pnl_pct >= tp:
                pnl = ((price - pos["entry"]) * pos["qty"] if pos["type"] == "long"
                       else (pos["entry"] - price) * pos["qty"])
                balance += pos["amount"] + pnl
                trades.append({"pnl": pnl, "type": pos["type"]})
                pos = None
                equity.append(balance)
                continue

        # Entry
        if not pos:
            if sig == "BUY":
                pos = {"type": "long",  "entry": price,
                       "qty": (balance * leverage) / price, "amount": balance}
                balance = 0
            elif sig == "SELL" and allow_short:
                pos = {"type": "short", "entry": price,
                       "qty": (balance * leverage) / price, "amount": balance}
                balance = 0

    # Tutup akhir
    if pos:
        price = closes[-1]
        pnl   = ((price - pos["entry"]) * pos["qty"] if pos["type"] == "long"
                 else (pos["entry"] - price) * pos["qty"])
        balance += pos["amount"] + pnl
        trades.append({"pnl": pnl, "type": pos["type"]})
        equity.append(balance)

    return {
        "cagr":    cagr(INITIAL, balance),
        "final":   round(balance, 2),
        "ret":     round((balance - INITIAL) / INITIAL * 100, 1),
        "dd":      max_drawdown(equity),
        "wr":      winrate(trades),
        "trades":  len(trades),
    }

# ── Grid Search SL/TP ─────────────────────────────────────────────────────────

def grid_search(df, leverage, allow_short=True, use_momentum=False,
                sl_range=None, tp_range=None):
    sl_range = sl_range or [2, 3, 4, 5, 6, 8, 10, 12, 15]
    tp_range = tp_range or [5, 8, 10, 12, 15, 20, 25, 30]
    best = {"cagr": -999}
    for sl in sl_range:
        for tp in tp_range:
            if tp <= sl: continue
            r = run(df, sl, tp, leverage, allow_short, use_momentum)
            if r["cagr"] > best["cagr"]:
                best = {**r, "sl": sl, "tp": tp}
    return best

# ── Main ──────────────────────────────────────────────────────────────────────

def test_all(name, symbol, asset_type, base_sl, base_tp):
    print(f"\n{'='*65}")
    print(f"  {name} ({symbol})")
    print(f"{'='*65}")

    df = load_data(asset_type, symbol, START, END, timeframe="1d")
    if df is None or len(df) < 300:
        print("  ❌ Data tidak cukup"); return

    results = {}

    # Buy & Hold benchmark per leverage
    print(f"\n  📌 BUY & HOLD BENCHMARK:")
    for lev in [1, 3, 5, 10]:
        c, r = bh_cagr(df, lev)
        print(f"     {lev}x leverage → CAGR {c:.1f}% | Return {r:.1f}%")
    bh3, _ = bh_cagr(df, 3)

    print(f"\n  {'─'*62}")

    # ── TEST A: Momentum Strategy (3x) ──
    r = run(df, base_sl, base_tp, 3, allow_short=False, use_momentum=True)
    results["A_Momentum_LongOnly_3x"] = r
    print(f"  A. Momentum Long-Only 3x    | CAGR:{r['cagr']:6.1f}% | DD:{r['dd']:6.1f}% | WR:{r['wr']:5.1f}% | T:{r['trades']}")

    r = run(df, base_sl, base_tp, 3, allow_short=True, use_momentum=True)
    results["A_Momentum_LongShort_3x"] = r
    print(f"  A. Momentum Long+Short 3x   | CAGR:{r['cagr']:6.1f}% | DD:{r['dd']:6.1f}% | WR:{r['wr']:5.1f}% | T:{r['trades']}")

    # ── TEST B: Higher Leverage ──
    print(f"  {'─'*62}")
    for lev in [5, 7, 10]:
        r = run(df, base_sl, base_tp, lev, allow_short=False)
        results[f"B_LongOnly_{lev}x"] = r
        print(f"  B. Long-Only {lev}x              | CAGR:{r['cagr']:6.1f}% | DD:{r['dd']:6.1f}% | WR:{r['wr']:5.1f}% | T:{r['trades']}")

    # Momentum + higher leverage
    for lev in [5, 10]:
        r = run(df, base_sl, base_tp, lev, allow_short=False, use_momentum=True)
        results[f"B_Momentum_{lev}x"] = r
        print(f"  B. Momentum {lev}x               | CAGR:{r['cagr']:6.1f}% | DD:{r['dd']:6.1f}% | WR:{r['wr']:5.1f}% | T:{r['trades']}")

    # ── TEST C: SL/TP Grid Search (3x) ──
    print(f"  {'─'*62}")
    print(f"  C. Grid Search SL/TP (3x, Long-Only)...")
    best_c = grid_search(df, 3, allow_short=False)
    results["C_GridSearch_3x"] = best_c
    print(f"  C. Best Grid 3x Long-Only   | CAGR:{best_c['cagr']:6.1f}% | DD:{best_c['dd']:6.1f}% | WR:{best_c['wr']:5.1f}% | SL:{best_c['sl']}% TP:{best_c['tp']}%")

    print(f"  C. Grid Search SL/TP (3x, Momentum)...")
    best_cm = grid_search(df, 3, allow_short=False, use_momentum=True)
    results["C_GridMomentum_3x"] = best_cm
    print(f"  C. Best Grid Momentum 3x    | CAGR:{best_cm['cagr']:6.1f}% | DD:{best_cm['dd']:6.1f}% | WR:{best_cm['wr']:5.1f}% | SL:{best_cm['sl']}% TP:{best_cm['tp']}%")

    # ── TEST D: Kombinasi Terbaik ──
    print(f"  {'─'*62}")
    # Ambil SL/TP terbaik dari grid, test di berbagai leverage
    best_sl = best_cm["sl"]
    best_tp = best_cm["tp"]
    for lev in [3, 5, 7, 10]:
        r = run(df, best_sl, best_tp, lev, allow_short=False, use_momentum=True)
        results[f"D_BestParams_{lev}x"] = r
        beat = "✅" if r["cagr"] > bh3 else "  "
        print(f"  D. Best Params Momentum {lev}x  {beat}| CAGR:{r['cagr']:6.1f}% | DD:{r['dd']:6.1f}% | WR:{r['wr']:5.1f}% | SL:{best_sl}% TP:{best_tp}%")

    # ── Winner ──
    best_name = max(results, key=lambda k: results[k]["cagr"])
    best_val  = results[best_name]["cagr"]
    beat_bh   = "✅ BEAT" if best_val > bh3 else "❌ BELUM BEAT"
    print(f"\n  🏆 TERBAIK: {best_name}")
    print(f"     CAGR: {best_val:.1f}% | B&H 3x: {bh3:.1f}% | {beat_bh}")

    return results, bh3

if __name__ == "__main__":
    print("\n" + "="*65)
    print("  ADVANCED STRATEGY COMPARISON")
    print(f"  Periode: {START} → {END}")
    print("="*65)

    assets = [
        ("Bitcoin",  "BTC/USDT", "crypto", 5.0, 10.0),
        ("Gold",     "GC=F",     "stock",  5.0, 10.0),
        ("S&P 500",  "^GSPC",    "stock",  4.0,  5.0),
    ]

    summary = []
    for name, sym, atype, sl, tp in assets:
        res = test_all(name, sym, atype, sl, tp)
        if res:
            results, bh = res
            best = max(results, key=lambda k: results[k]["cagr"])
            summary.append({
                "aset": name, "bh": bh,
                "best": best, "best_cagr": results[best]["cagr"],
                "beat": results[best]["cagr"] > bh
            })

    print("\n" + "="*65)
    print("  RINGKASAN FINAL")
    print("="*65)
    for s in summary:
        status = "✅ BEAT!" if s["beat"] else "❌ Belum"
        print(f"  {s['aset']:10} | B&H 3x: {s['bh']:6.1f}% | Best: {s['best_cagr']:6.1f}% ({s['best'][:25]}) | {status}")

    print("\n  ⚠️  Catatan:")
    print("  - DD tinggi di leverage besar = risiko likuidasi nyata")
    print("  - Beat B&H bukan berarti strategi lebih baik jika DD > 50%")
    print("  - Risk-adjusted return (Sharpe) lebih penting dari CAGR mentah")