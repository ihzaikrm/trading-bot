# validate_strategies.py
# Validasi out-of-sample (2020-2024) + Sharpe Ratio & risk-adjusted metrics

import sys, os
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np
from backtest.data_loader import load_data
from core.indicators import calc_indicators

INITIAL = 1000.0
RISK_FREE_RATE = 0.05  # 5% per tahun (US Treasury)

# ── Helpers ──────────────────────────────────────────────────────────────────

def cagr(initial, final, years):
    if final <= 0 or initial <= 0: return -99.9
    return round(((final / initial) ** (1 / years) - 1) * 100, 1)

def max_drawdown(equity_curve):
    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak * 100
    return round(float(dd.min()), 1)

def sharpe_ratio(equity_curve, years, rfr=RISK_FREE_RATE):
    """Sharpe = (Return - RiskFree) / Volatility"""
    eq = np.array(equity_curve)
    if len(eq) < 2: return 0.0
    daily_returns = np.diff(eq) / eq[:-1]
    if daily_returns.std() == 0: return 0.0
    annual_return = (eq[-1] / eq[0]) ** (1 / years) - 1
    annual_vol    = daily_returns.std() * np.sqrt(252)
    sharpe        = (annual_return - rfr) / annual_vol
    return round(sharpe, 2)

def sortino_ratio(equity_curve, years, rfr=RISK_FREE_RATE):
    """Sortino = (Return - RiskFree) / Downside Volatility"""
    eq = np.array(equity_curve)
    if len(eq) < 2: return 0.0
    daily_returns  = np.diff(eq) / eq[:-1]
    downside       = daily_returns[daily_returns < 0]
    if len(downside) == 0 or downside.std() == 0: return 0.0
    annual_return  = (eq[-1] / eq[0]) ** (1 / years) - 1
    downside_vol   = downside.std() * np.sqrt(252)
    return round((annual_return - rfr) / downside_vol, 2)

def calmar_ratio(annual_cagr, max_dd):
    """Calmar = CAGR / MaxDrawdown — semakin tinggi semakin baik"""
    if max_dd == 0: return 0.0
    return round(annual_cagr / abs(max_dd), 3)

def winrate(trades):
    if not trades: return 0.0
    return round(sum(1 for t in trades if t["pnl"] > 0) / len(trades) * 100, 1)

def avg_win_loss(trades):
    wins   = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    avg_w  = round(np.mean(wins), 2)   if wins   else 0
    avg_l  = round(np.mean(losses), 2) if losses else 0
    ratio  = round(abs(avg_w / avg_l), 2) if avg_l != 0 else 0
    return avg_w, avg_l, ratio

def bh_metrics(df, leverage, years):
    eq = []
    start = df["close"].iloc[0]
    for price in df["close"]:
        ret    = (price - start) / start * leverage
        equity = INITIAL * (1 + ret)
        eq.append(max(equity, 0.01))
    final = eq[-1]
    c     = cagr(INITIAL, final, years)
    dd    = max_drawdown(eq)
    sr    = sharpe_ratio(eq, years)
    so    = sortino_ratio(eq, years)
    cal   = calmar_ratio(c, dd)
    return {"cagr": c, "dd": dd, "sharpe": sr, "sortino": so, "calmar": cal, "final": round(final, 2)}

# ── Signals ──────────────────────────────────────────────────────────────────

def signal_momentum(ind, allow_short=True):
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

# ── Backtest Engine ───────────────────────────────────────────────────────────

def run(df, sl, tp, leverage, allow_short=True, use_momentum=False, years=None):
    closes  = df["close"].tolist()
    balance = INITIAL
    pos     = None
    trades  = []
    equity  = [INITIAL]

    for i in range(200, len(closes)):
        price = closes[i]
        ind   = calc_indicators(closes[:i+1])
        if ind is None: continue

        sig = (signal_momentum(ind, allow_short)
               if use_momentum else
               signal_standard(ind, allow_short))

        # SL/TP
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

    years  = years or YEARS
    c      = cagr(INITIAL, balance, years)
    dd     = max_drawdown(equity)
    sr     = sharpe_ratio(equity, years)
    so     = sortino_ratio(equity, years)
    cal    = calmar_ratio(c, dd)
    avg_w, avg_l, wr_ratio = avg_win_loss(trades)

    return {
        "cagr": c, "final": round(balance, 2),
        "dd": dd, "sharpe": sr, "sortino": so, "calmar": cal,
        "wr": winrate(trades), "trades": len(trades),
        "avg_win": avg_w, "avg_loss": avg_l, "wr_ratio": wr_ratio,
        "equity": equity
    }

# ── Print Result ──────────────────────────────────────────────────────────────

def print_result(label, r, bh, label_width=30):
    beat = "✅" if r["cagr"] > bh["cagr"] else "❌"
    sharpe_grade = ("🟢" if r["sharpe"] > 1.5 else
                    "🟡" if r["sharpe"] > 0.8 else "🔴")
    print(f"  {label:<{label_width}} | CAGR:{r['cagr']:6.1f}% {beat} "
          f"| DD:{r['dd']:6.1f}% "
          f"| Sharpe:{r['sharpe']:5.2f}{sharpe_grade} "
          f"| Sortino:{r['sortino']:5.2f} "
          f"| Calmar:{r['calmar']:5.3f} "
          f"| WR:{r['wr']:5.1f}% | T:{r['trades']}")

# ── Test Per Aset ──────────────────────────────────────────────────────────────

def validate_asset(name, symbol, asset_type,
                   # Parameter optimal dari backtest sebelumnya
                   opt_sl, opt_tp, opt_momentum, opt_allow_short):

    print(f"\n{'='*110}")
    print(f"  {name} ({symbol})")
    print(f"{'='*110}")

    periods = [
        ("In-Sample   2015-2020", "2015-01-01", "2020-01-01", 5),
        ("Out-of-Sample 2020-2024", "2020-01-01", "2024-12-31", 4),
        ("Full Period  2015-2024", "2015-01-01", "2024-12-31", 10),
    ]

    for period_name, start, end, years in periods:
        print(f"\n  📅 {period_name}")
        print(f"  {'─'*107}")

        df = load_data(asset_type, symbol, start, end, timeframe="1d")
        if df is None or len(df) < 250:
            print("  ❌ Data tidak cukup"); continue

        # Buy & Hold benchmark
        bh = bh_metrics(df, 3, years)
        print(f"  {'B&H 3x (benchmark)':<30} | CAGR:{bh['cagr']:6.1f}%    "
              f"| DD:{bh['dd']:6.1f}% "
              f"| Sharpe:{bh['sharpe']:5.2f}   "
              f"| Sortino:{bh['sortino']:5.2f} "
              f"| Calmar:{bh['calmar']:5.3f}")
        print(f"  {'─'*107}")

        # Strategi optimal
        r_opt = run(df, opt_sl, opt_tp, 3,
                    allow_short=opt_allow_short,
                    use_momentum=opt_momentum,
                    years=years)
        print_result(f"Optimal (SL:{opt_sl}% TP:{opt_tp}%)", r_opt, bh)

        # Baseline (kondisi bot sekarang)
        r_base = run(df, 5.0, 10.0, 3, allow_short=True, use_momentum=False, years=years)
        print_result("Baseline (SL:5% TP:10%)", r_base, bh)

        # Momentum Long-Only
        r_mom = run(df, opt_sl, opt_tp, 3, allow_short=False, use_momentum=True, years=years)
        print_result(f"Momentum Long-Only", r_mom, bh)

        # Detail win/loss untuk strategi optimal
        print(f"\n     💰 Optimal Detail: AvgWin=${r_opt['avg_win']} | "
              f"AvgLoss=${r_opt['avg_loss']} | "
              f"W/L Ratio:{r_opt['wr_ratio']}x | "
              f"Final Balance:${r_opt['final']}")

    print()

# ── Main ──────────────────────────────────────────────────────────────────────

YEARS = 10

if __name__ == "__main__":
    print("\n" + "="*110)
    print("  VALIDASI OUT-OF-SAMPLE + RISK-ADJUSTED METRICS")
    print("  Sharpe >1.5=Excellent | >0.8=Good | <0.5=Poor")
    print("  Calmar = CAGR/MaxDD (semakin tinggi semakin baik)")
    print("  Sortino = seperti Sharpe tapi hanya hitung downside risk")
    print("="*110)

    # Parameter optimal dari hasil backtest sebelumnya
    assets = [
        # name, symbol, type, opt_sl, opt_tp, use_momentum, allow_short
        ("Bitcoin",  "BTC/USDT", "crypto", 6.0,  30.0, True,  False),
        ("Gold",     "GC=F",     "stock",  8.0,  30.0, False, True),
        ("S&P 500",  "^GSPC",    "stock",  10.0, 30.0, True,  False),
    ]

    for name, sym, atype, sl, tp, mom, ashort in assets:
        validate_asset(name, sym, atype, sl, tp, mom, ashort)

    print("="*110)
    print("  PANDUAN INTERPRETASI:")
    print("  ✅ = Beat Buy & Hold CAGR")
    print("  🟢 Sharpe >1.5 = Excellent risk-adjusted return")
    print("  🟡 Sharpe 0.8-1.5 = Good")
    print("  🔴 Sharpe <0.8 = Poor (return tidak sebanding risiko)")
    print("  Calmar >0.5 = Bagus | Calmar >1.0 = Sangat bagus")
    print("="*110)