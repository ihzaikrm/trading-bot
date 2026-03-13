# core/strategy_manager.py
# Auto-Strategy Manager dengan quarterly evaluation & regime detection
# Terinspirasi dari strategi hedge fund: Turtle, Dual Momentum, Mean Reversion

import json
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

STRATEGY_LOG_FILE = "logs/strategy_state.json"

# ─── Strategy Library ─────────────────────────────────────────────────────────

def sig_volume_momentum(ind, closes, volumes=None, allow_short=False):
    """BTC: Momentum + Volume Filter (Score 8/14)"""
    score = 0
    if ind["ema_trend"] == "BULLISH": score += 3
    elif ind["ema_trend"] == "BEARISH": score -= 3
    if ind["macd_cross"] == "BULLISH": score += 2
    else: score -= 2
    if ind["rsi"] < 30: score += 1
    elif ind["rsi"] > 70: score -= 1

    # Volume filter: hanya trade kalau volume di atas median
    if volumes and len(volumes) >= 20:
        vol_median = np.median(volumes[-20:])
        if volumes[-1] < vol_median:
            return "HOLD"

    if score >= 3: return "BUY"
    if score <= -3 and allow_short: return "SELL"
    return "HOLD"

def sig_turtle(ind, closes, allow_short=False, period=20):
    """SPX: Turtle Breakout (Score 7/14)
    Richard Dennis strategy — breakout 20-day high/low"""
    if len(closes) < period + 1: return "HOLD"
    high_n = max(closes[-(period+1):-1])
    low_n  = min(closes[-(period+1):-1])
    price  = closes[-1]
    if price > high_n: return "BUY"
    if price < low_n and allow_short: return "SELL"
    return "HOLD"

def sig_mean_reversion(ind, closes, allow_short=True, z_threshold=2.0):
    """Mean Reversion: entry saat harga menyimpang 2σ dari mean"""
    if len(closes) < 20: return "HOLD"
    s    = pd.Series(closes[-50:])
    ma   = s.rolling(20).mean().iloc[-1]
    std  = s.rolling(20).std().iloc[-1]
    if std == 0: return "HOLD"
    z    = (closes[-1] - ma) / std
    if z < -z_threshold: return "BUY"
    if z > z_threshold and allow_short: return "SELL"
    return "HOLD"

def sig_dual_momentum(ind, closes, allow_short=False):
    """Gary Antonacci Dual Momentum"""
    if len(closes) < 252: return "HOLD"
    ret_12m = (closes[-1] - closes[-252]) / closes[-252]
    ret_1m  = (closes[-1] - closes[-21])  / closes[-21]
    if ret_12m > 0 and ret_1m > 0: return "BUY"
    if ret_12m < 0 and allow_short: return "SELL"
    return "HOLD"

def sig_combined_hf(ind, closes, allow_short=False):
    """Turtle + Dual Momentum + EMA — high conviction only"""
    if len(closes) < 252: return "HOLD"
    turtle = sig_turtle(ind, closes, allow_short)
    dual   = sig_dual_momentum(ind, closes, allow_short)
    ema_ok = ind["ema_trend"] == "BULLISH"
    if turtle == "BUY" and dual == "BUY" and ema_ok: return "BUY"
    if turtle == "SELL" and dual == "SELL" and allow_short: return "SELL"
    return "HOLD"

def sig_strong_confirm(ind, closes=None, allow_short=False):
    """4+ indikator harus sepakat — untuk aset ranging seperti Gold"""
    votes_buy = votes_sell = 0
    if ind["rsi"] < 30: votes_buy  += 1
    elif ind["rsi"] > 70: votes_sell += 1
    if ind["macd_cross"] == "BULLISH": votes_buy  += 1
    else: votes_sell += 1
    if ind["ema_trend"] == "BULLISH": votes_buy  += 1
    elif ind["ema_trend"] == "BEARISH": votes_sell += 1
    if ind["bb_pos"] == "OVERSOLD": votes_buy  += 1
    elif ind["bb_pos"] == "OVERBOUGHT": votes_sell += 1
    if ind["stoch_signal"] == "OVERSOLD": votes_buy  += 1
    elif ind["stoch_signal"] == "OVERBOUGHT": votes_sell += 1
    if votes_buy  >= 4: return "BUY"
    if votes_sell >= 4 and allow_short: return "SELL"
    return "HOLD"

# Registry semua strategi
STRATEGY_REGISTRY = {
    "volume_momentum": sig_volume_momentum,
    "turtle":          sig_turtle,
    "mean_reversion":  sig_mean_reversion,
    "dual_momentum":   sig_dual_momentum,
    "combined_hf":     sig_combined_hf,
    "strong_confirm":  sig_strong_confirm,
}

# Default strategi per aset (hasil backtest)
DEFAULT_STRATEGIES = {
    "BTC/USDT": "volume_momentum",
    "XAUUSD":   "strong_confirm",
    "SPX":      "turtle",
    # Aset baru
    "ETH/USDT": "volume_momentum",
    "NDX":      "turtle",
}

# ─── Regime Detector ──────────────────────────────────────────────────────────

def detect_regime(closes):
    """
    Deteksi market regime:
    BULL  → trend-following strategies (turtle, momentum)
    BEAR  → defensive / mean reversion
    SIDEWAYS → mean reversion / strong confirm
    """
    if len(closes) < 200: return "UNKNOWN"
    s      = pd.Series(closes)
    ema50  = float(s.ewm(span=50).mean().iloc[-1])
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]
    ret_3m = (closes[-1] - closes[-63]) / closes[-63] if len(closes) >= 63 else 0
    ret_1m = (closes[-1] - closes[-21]) / closes[-21] if len(closes) >= 21 else 0
    vol_20 = pd.Series(closes[-20:]).pct_change().std() * np.sqrt(252) if len(closes) >= 20 else 0

    if price > ema200 and ema50 > ema200 and ret_3m > 0.05:
        return "BULL"
    elif price < ema200 and ema50 < ema200 and ret_3m < -0.05:
        return "BEAR"
    elif vol_20 < 0.15 and abs(ret_3m) < 0.05:
        return "SIDEWAYS"
    else:
        return "TRANSITIONING"

def regime_to_strategy(regime, asset_symbol):
    """Map regime ke strategi terbaik"""
    regime_map = {
        "BULL":         "turtle",          # Trend-following di bull market
        "BEAR":         "mean_reversion",  # Reversion setelah oversold
        "SIDEWAYS":     "mean_reversion",  # Range-bound → mean reversion
        "TRANSITIONING":"strong_confirm",  # Tidak jelas → tunggu konfirmasi kuat
        "UNKNOWN":      DEFAULT_STRATEGIES.get(asset_symbol, "strong_confirm"),
    }
    return regime_map.get(regime, "strong_confirm")

# ─── Performance Tracker ──────────────────────────────────────────────────────

def calculate_strategy_performance(trades_history, strategy_name, days=90):
    """Hitung performa strategi dalam N hari terakhir"""
    if not trades_history:
        return {"cagr": 0, "sharpe": 0, "winrate": 0, "trades": 0}

    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = [t for t in trades_history
              if t.get("strategy") == strategy_name
              and datetime.fromisoformat(t.get("exit_date","2000-01-01")) > cutoff
              and t.get("pnl") is not None]

    if not recent:
        return {"cagr": 0, "sharpe": 0, "winrate": 0, "trades": 0}

    pnls    = [t["pnl"] for t in recent]
    wins    = sum(1 for p in pnls if p > 0)
    winrate = wins / len(pnls) * 100 if pnls else 0
    total_return = sum(pnls)

    # Annualized return sederhana
    annual_factor = 365 / days
    cagr_est = total_return * annual_factor

    return {
        "cagr":    round(cagr_est, 2),
        "winrate": round(winrate, 1),
        "trades":  len(recent),
        "total_pnl": round(total_return, 2),
    }

# ─── Quarterly Evaluator ──────────────────────────────────────────────────────

def quarterly_evaluation(symbol, trades_history, closes, current_strategy):
    """
    Evaluasi strategi setiap kuartal (90 hari).
    Bandingkan semua strategi berdasarkan trade history & regime saat ini.
    Return: strategi terbaik untuk kuartal berikutnya.
    """
    print(f"\n  📊 QUARTERLY EVALUATION: {symbol}")
    print(f"  {'─'*50}")

    # 1. Deteksi regime saat ini
    regime = detect_regime(closes)
    print(f"  Market Regime: {regime}")

    # 2. Hitung performa tiap strategi dari trade history
    strategy_scores = {}
    for strat_name in STRATEGY_REGISTRY:
        perf = calculate_strategy_performance(trades_history, strat_name, days=90)
        strategy_scores[strat_name] = perf
        if perf["trades"] > 0:
            print(f"  {strat_name:<20} | Trades:{perf['trades']:3d} "
                  f"| WR:{perf['winrate']:5.1f}% "
                  f"| PnL:${perf['total_pnl']:8.2f}")

    # 3. Pilih strategi berdasarkan:
    #    a) Jika ada cukup data trade (>5 trades) → pilih yang terbaik dari history
    #    b) Jika tidak → gunakan regime-based recommendation
    strategies_with_data = {k: v for k, v in strategy_scores.items()
                             if v["trades"] >= 5}

    if strategies_with_data:
        # Scoring: winrate * 0.4 + pnl_normalized * 0.6
        max_pnl = max(abs(v["total_pnl"]) for v in strategies_with_data.values()) or 1
        scored  = {
            k: (v["winrate"] * 0.4 + (v["total_pnl"] / max_pnl * 100) * 0.6)
            for k, v in strategies_with_data.items()
        }
        best_from_history = max(scored, key=scored.get)
    else:
        best_from_history = None

    # 4. Regime recommendation
    regime_recommend = regime_to_strategy(regime, symbol)

    # 5. Final decision: kombinasikan keduanya
    if best_from_history and best_from_history != current_strategy:
        recommended = best_from_history
        reason      = f"history ({strategy_scores[best_from_history]['trades']} trades)"
    elif regime_recommend != current_strategy:
        recommended = regime_recommend
        reason      = f"regime ({regime})"
    else:
        recommended = current_strategy
        reason      = "no change needed"

    print(f"  Regime recommendation: {regime_recommend}")
    print(f"  History best:          {best_from_history or 'insufficient data'}")
    print(f"  ➜ Decision: {recommended} [{reason}]")

    return recommended, regime, {
        "symbol":         symbol,
        "evaluated_at":   datetime.utcnow().isoformat(),
        "regime":         regime,
        "old_strategy":   current_strategy,
        "new_strategy":   recommended,
        "reason":         reason,
    }

# ─── State Manager ────────────────────────────────────────────────────────────

def load_strategy_state():
    """Load current strategy assignments dari file"""
    if os.path.exists(STRATEGY_LOG_FILE):
        try:
            with open(STRATEGY_LOG_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "assignments":       DEFAULT_STRATEGIES.copy(),
        "last_evaluated":    {},
        "evaluation_history":[],
        "regime_history":    {},
    }

def save_strategy_state(state):
    os.makedirs("logs", exist_ok=True)
    with open(STRATEGY_LOG_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_current_strategy(symbol):
    """Ambil strategi aktif untuk aset tertentu"""
    state = load_strategy_state()
    return state["assignments"].get(symbol, DEFAULT_STRATEGIES.get(symbol, "strong_confirm"))

def should_evaluate(symbol, interval_days=90):
    """Cek apakah sudah waktunya evaluasi quarterly"""
    state = load_strategy_state()
    last  = state["last_evaluated"].get(symbol)
    if not last:
        return True
    last_dt = datetime.fromisoformat(last)
    return (datetime.utcnow() - last_dt).days >= interval_days

# ─── Main Interface ───────────────────────────────────────────────────────────

def get_signal(symbol, ind, closes, volumes=None, allow_short=False):
    """
    Interface utama — dipanggil dari signal_engine.py
    Otomatis memilih strategi yang tepat untuk aset & kondisi pasar.
    """
    strategy_name = get_current_strategy(symbol)
    sig_fn        = STRATEGY_REGISTRY.get(strategy_name, sig_strong_confirm)

    # Jalankan strategi
    try:
        if strategy_name == "volume_momentum" and volumes:
            signal = sig_fn(ind, closes, volumes=volumes, allow_short=allow_short)
        else:
            signal = sig_fn(ind, closes, allow_short=allow_short)
    except Exception as e:
        print(f"  ⚠️ Strategy error ({strategy_name}): {e}, fallback to strong_confirm")
        signal = sig_strong_confirm(ind, closes, allow_short=allow_short)

    return signal, strategy_name

def run_quarterly_check(symbol, closes, trades_history):
    """
    Jalankan quarterly check. Dipanggil dari bot.py setiap run,
    tapi hanya aktif setiap 90 hari.
    """
    if not should_evaluate(symbol):
        return None

    state            = load_strategy_state()
    current_strategy = state["assignments"].get(symbol, DEFAULT_STRATEGIES.get(symbol))

    new_strategy, regime, eval_record = quarterly_evaluation(
        symbol, trades_history, closes, current_strategy
    )

    # Update state
    state["assignments"][symbol]        = new_strategy
    state["last_evaluated"][symbol]     = datetime.utcnow().isoformat()
    state["regime_history"][symbol]     = regime
    state["evaluation_history"].append(eval_record)

    # Simpan hanya 20 history terakhir
    state["evaluation_history"] = state["evaluation_history"][-20:]

    save_strategy_state(state)

    changed = new_strategy != current_strategy
    return {
        "changed":      changed,
        "old":          current_strategy,
        "new":          new_strategy,
        "regime":       regime,
        "eval_record":  eval_record,
    }

def get_strategy_status():
    """Untuk Telegram /strategy command"""
    state = load_strategy_state()
    lines = ["📊 *STRATEGY STATUS*\n"]
    for symbol, strat in state["assignments"].items():
        regime  = state["regime_history"].get(symbol, "UNKNOWN")
        last_ev = state["last_evaluated"].get(symbol, "Never")
        if last_ev != "Never":
            last_ev = last_ev[:10]
        next_ev = "N/A"
        if last_ev != "Never":
            try:
                next_dt = datetime.fromisoformat(
                    state["last_evaluated"][symbol]) + timedelta(days=90)
                next_ev = next_dt.strftime("%Y-%m-%d")
            except:
                pass
        lines.append(
            f"*{symbol}*\n"
            f"  Strategy: `{strat}`\n"
            f"  Regime: `{regime}`\n"
            f"  Last eval: `{last_ev}`\n"
            f"  Next eval: `{next_ev}`\n"
        )

    # Recent changes
    history = state.get("evaluation_history", [])
    changes = [h for h in history if h.get("old_strategy") != h.get("new_strategy")]
    if changes:
        lines.append("📝 *Recent Strategy Changes:*")
        for c in changes[-3:]:
            lines.append(
                f"  {c['symbol']}: `{c['old_strategy']}` → `{c['new_strategy']}` "
                f"({c['evaluated_at'][:10]}, {c['reason']})"
            )
    return "\n".join(lines)