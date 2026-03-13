# backtest/engine.py
# ✅ FIXED: Engine sekarang pakai strategi final per aset yang sama dengan bot.py
# (bukan rule_based_signal generic yang lama)

import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.indicators import calc_indicators

# ----------------------------------------------------------------------
# Strategi final per aset — IDENTIK dengan core/signal_engine.py
# (copy di sini agar backtest tidak bergantung pada async/LLM imports)
# ----------------------------------------------------------------------

def _sig_btc_vol_tsmom(ind, closes, volumes):
    """BTC: Vol-Weighted TSMOM (Huang et al. 2024, Score 8/14)"""
    if len(closes) < 30 or len(volumes) < 20:
        return "HOLD"
    ret_30d   = (closes[-1] - closes[-30]) / closes[-30]
    ret_7d    = (closes[-1] - closes[-7])  / closes[-7]
    vol_ratio = volumes[-1] / (np.median(volumes[-20:]) + 1e-9)
    vol_strong = vol_ratio > 1.2
    score = 0
    if ret_30d > 0:   score += 2
    elif ret_30d < 0: score -= 2
    if ret_7d > 0:    score += 1
    elif ret_7d < 0:  score -= 1
    if ind["ema_trend"] == "BULLISH":   score += 2
    elif ind["ema_trend"] == "BEARISH": score -= 2
    if ind["macd_cross"] == "BULLISH":  score += 1
    else:                               score -= 1
    if vol_strong: score += 2
    if score >= 5:
        return "BUY"
    return "HOLD"


def _sig_gold_smart_hold(ind, closes, date=None):
    """Gold: Smart Hold (Baur et al. 2020)"""
    if len(closes) < 200:
        return "HOLD"
    if date is not None:
        ts = pd.Timestamp(date)
        if ts.month in [3, 4, 5, 6]:
            return "HOLD"   # Skip bear season Mar-Jun
        if ts.weekday() == 0:
            return "HOLD"   # No Monday
    s      = pd.Series(closes)
    ema50  = float(s.ewm(span=50).mean().iloc[-1])
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]
    ret_3m = (closes[-1] - closes[-63]) / closes[-63] if len(closes) >= 63 else 0
    ret_1m = (closes[-1] - closes[-21]) / closes[-21] if len(closes) >= 21 else 0
    if ret_3m < -0.08 and ret_1m < -0.03:
        return "HOLD"   # Prolonged bear exit
    conditions = sum([
        price > ema200,
        ema50 > ema200,
        ret_3m > 0.03,
        ret_1m > 0,
        ind["ema_trend"] == "BULLISH",
        ind["macd_cross"] == "BULLISH",
    ])
    if conditions >= 5:
        return "BUY"
    return "HOLD"


def _sig_spx_monthly_seasonal(ind, closes, date):
    """SPX: Monthly Seasonal R8 (Vojtko & Padysak SSRN, Score 7/14)"""
    if len(closes) < 21:
        return "HOLD"
    month = pd.Timestamp(date).month
    if month in [6, 9]:
        return "HOLD"   # Skip Jun & Sep (worst months)
    STRONG = [1, 4, 7, 11]
    score = 0
    high20 = max(closes[-21:-1])
    if closes[-1] > high20:            score += 3
    if ind["ema_trend"] == "BULLISH":  score += 2
    if ind["macd_cross"] == "BULLISH": score += 1
    if ind["rsi"] > 50:                score += 1
    if month in STRONG:                score += 1
    if score >= 5:
        return "BUY"
    return "HOLD"


# Map symbol → strategi
STRATEGY_MAP = {
    "BTC/USDT": ("btc",  _sig_btc_vol_tsmom),
    "GC=F":     ("gold", _sig_gold_smart_hold),
    "^GSPC":    ("spx",  _sig_spx_monthly_seasonal),
}

def get_signal_for_symbol(symbol, ind, closes, volumes, date):
    """Pilih dan jalankan strategi yang benar per aset."""
    if symbol not in STRATEGY_MAP:
        # Fallback generic jika aset tidak dikenali
        score = 0
        if ind["rsi"] < 35:              score += 2
        elif ind["rsi"] > 65:            score -= 2
        if ind["macd_cross"] == "BULLISH": score += 1
        else:                            score -= 1
        if ind["ema_trend"] == "BULLISH":  score += 1
        elif ind["ema_trend"] == "BEARISH": score -= 1
        return "BUY" if score >= 3 else "HOLD"

    kind, fn = STRATEGY_MAP[symbol]
    if kind == "btc":
        return fn(ind, closes, volumes)
    elif kind == "gold":
        return fn(ind, closes, date)
    else:  # spx
        return fn(ind, closes, date)


# ----------------------------------------------------------------------
# Backtest engine utama
# ----------------------------------------------------------------------

def backtest(symbol, asset_type, start_date, end_date,
             sl_pct=2.0, tp_pct=5.0, leverage=1,
             initial_balance=1000.0, position_size_pct=100.0):
    """
    Jalankan backtest untuk satu aset menggunakan strategi final per aset.
    Long-only (sesuai strategi riset — tidak ada SHORT).

    position_size_pct: % dari balance yang digunakan per trade (default 100%).
    Leverage di-apply hanya pada position_size, bukan seluruh balance.
    Contoh: balance=$1000, position_size_pct=100, leverage=3
            → margin=$1000, exposure=$3000, max loss=$60 (SL 6% dari exposure)
    """
    from .data_loader import load_data

    df = load_data(asset_type, symbol, start_date, end_date, timeframe='1d')
    if df is None or len(df) < 50:
        print(f"[ERROR] Data tidak cukup untuk {symbol}")
        return None

    closes  = df['close'].tolist()
    volumes = df['volume'].tolist() if 'volume' in df.columns else [1.0] * len(closes)
    dates   = df.index.tolist()

    balance      = initial_balance
    position     = None
    trades       = []
    equity_curve = [balance]

    # Mulai dari bar ke-200 agar semua strategi punya cukup data
    start_idx = 200

    for i in range(start_idx, len(closes)):
        current_price = closes[i]
        current_date  = dates[i]
        closes_so_far  = closes[:i+1]
        volumes_so_far = volumes[:i+1]

        ind = calc_indicators(closes_so_far)
        if ind is None:
            equity_curve.append(
                balance if not position
                else balance + position['margin'] +
                     (current_price - position['entry']) * position['qty']
            )
            continue

        signal = get_signal_for_symbol(
            symbol, ind, closes_so_far, volumes_so_far, current_date
        )

        # --- Cek SL/TP jika ada posisi ---
        if position:
            # PnL dihitung dari exposure (margin * leverage)
            pnl_pct = (current_price - position['entry']) / position['entry'] * 100 * leverage

            hit_sl = pnl_pct <= -sl_pct
            hit_tp = pnl_pct >= tp_pct

            if hit_sl or hit_tp:
                # PnL riil = perubahan harga × qty
                pnl = (current_price - position['entry']) * position['qty']
                # Kembalikan margin (bukan seluruh balance) + PnL
                balance += position['margin'] + pnl
                trades.append({
                    'entry_date': dates[position['idx']],
                    'exit_date':  current_date,
                    'type':       'long',
                    'entry':      position['entry'],
                    'exit':       current_price,
                    'qty':        position['qty'],
                    'margin':     position['margin'],
                    'pnl':        pnl,
                    'pnl_pct':    pnl_pct,
                    'reason':     'SL' if hit_sl else 'TP',
                })
                position = None
                equity_curve.append(balance)
                continue

        # --- Entry jika sinyal BUY dan belum ada posisi ---
        if not position and signal == 'BUY' and balance > 0:
            # Margin = porsi balance yang digunakan (position_size_pct%)
            margin = balance * (position_size_pct / 100.0)
            # Exposure = margin × leverage (ini yang digunakan untuk beli)
            exposure = margin * leverage
            qty = exposure / current_price
            position = {
                'type':   'long',
                'entry':  current_price,
                'qty':    qty,
                'margin': margin,   # modal yang dikunci (bukan seluruh balance)
                'idx':    i,
            }
            # Kurangi balance dengan margin saja, sisanya tetap ada
            balance -= margin

        equity_curve.append(
            balance if not position
            else balance + position['margin'] +
                 (current_price - position['entry']) * position['qty']
        )

    # --- Tutup posisi di akhir periode ---
    if position:
        exit_price = closes[-1]
        pnl = (exit_price - position['entry']) * position['qty']
        pnl_pct = (exit_price - position['entry']) / position['entry'] * 100 * leverage
        balance += position['margin'] + pnl
        trades.append({
            'entry_date': dates[position['idx']],
            'exit_date':  dates[-1],
            'type':       'long',
            'entry':      position['entry'],
            'exit':       exit_price,
            'qty':        position['qty'],
            'margin':     position['margin'],
            'pnl':        pnl,
            'pnl_pct':    pnl_pct,
            'reason':     'End of data',
        })
        equity_curve.append(balance)

    # --- Hitung metrik ---
    total_return = (balance - initial_balance) / initial_balance * 100
    years = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25
    cagr  = ((balance / initial_balance) ** (1 / years) - 1) * 100 if years > 0 else 0

    wins     = [t for t in trades if t['pnl'] > 0]
    losses   = [t for t in trades if t['pnl'] <= 0]
    winrate  = len(wins) / len(trades) * 100 if trades else 0

    eq = pd.Series(equity_curve)
    rolling_max = eq.cummax()
    drawdown    = ((eq - rolling_max) / rolling_max * 100)
    max_dd      = drawdown.min()

    daily_returns = eq.pct_change().dropna()
    sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)
              if daily_returns.std() > 0 else 0)

    return {
        'symbol':          symbol,
        'start':           start_date,
        'end':             end_date,
        'initial_balance': initial_balance,
        'final_balance':   balance,
        'total_return':    total_return,
        'cagr':            cagr,
        'winrate':         winrate,
        'total_trades':    len(trades),
        'max_drawdown':    max_dd,
        'sharpe':          sharpe,
        'best_trade':      max((t['pnl'] for t in trades), default=0),
        'worst_trade':     min((t['pnl'] for t in trades), default=0),
        'trades':          trades,
        'equity_curve':    equity_curve,
    }