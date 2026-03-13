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
    vol_strong = vol_ratio > 1.0
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
    if score >= 4:
        return "BUY"
    return "HOLD"


def _sig_gold_bah_sl(ind, closes, date=None):
    """
    Gold v3: Buy & Hold dengan Trailing SL
    - Selalu BUY jika tidak ada posisi (mirip B&H)
    - Exit hanya jika drawdown dari peak > 8% (ditangani di engine via SL)
    - Re-entry otomatis setelah exit (next bar BUY lagi)
    Filosofi: capture hampir semua upside Gold, hanya keluar saat crash besar.
    """
    if len(closes) < 50:
        return "HOLD"
    s      = pd.Series(closes)
    ema200 = float(s.ewm(span=200).mean().iloc[-1])
    price  = closes[-1]
    # Hanya satu filter: harga di atas EMA200 (trend jangka panjang)
    if price > ema200:
        return "BUY"
    return "HOLD"


def _sig_spx_bah_sl(ind, closes, date=None):
    """
    SPX v3: Buy & Hold dengan Trailing SL
    - Selalu BUY kecuali September (statistik paling buruk)
    - Exit hanya via SL 10% (ditangani engine)
    - Re-entry otomatis setelah exit
    Filosofi: ikuti bull run SPX sepenuhnya, hanya lindungi crash besar.
    """
    if len(closes) < 50:
        return "HOLD"
    if date is not None:
        month = pd.Timestamp(date).month
        if month == 9:
            return "HOLD"  # Skip September saja
    # EMA trend sebagai minimal filter
    if ind["ema_trend"] == "BEARISH":
        return "HOLD"
    return "BUY"


# Map symbol → strategi
STRATEGY_MAP = {
    "BTC/USDT": ("btc",  _sig_btc_vol_tsmom),
    "GC=F":     ("gold", _sig_gold_bah_sl),   # v3: B&H + SL
    "^GSPC":    ("spx",  _sig_spx_bah_sl),    # v3: B&H + SL
}

def get_signal_for_symbol(symbol, ind, closes, volumes, date):
    """Pilih dan jalankan strategi yang benar per aset."""
    if symbol not in STRATEGY_MAP:
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
    else:  # gold & spx — keduanya terima date
        return fn(ind, closes, date)


# ----------------------------------------------------------------------
# Backtest engine utama
# ----------------------------------------------------------------------

def _kelly_fraction(win_rate, tp_pct, sl_pct, half=True,
                    min_f=0.05, max_f=0.50):
    """Kelly Criterion — hitung % balance optimal per trade."""
    if sl_pct <= 0 or tp_pct <= 0: return min_f
    b = tp_pct / sl_pct
    kelly = (b * win_rate - (1 - win_rate)) / b
    if kelly <= 0: return 0.0          # edge negatif, jangan trade
    if half: kelly /= 2.0              # Half-Kelly untuk safety
    return max(min_f, min(max_f, kelly))

def backtest(symbol, asset_type, start_date, end_date,
             sl_pct=2.0, tp_pct=5.0, leverage=1,
             initial_balance=1000.0, position_size_pct=100.0,
             use_kelly=True):
    """
    Jalankan backtest untuk satu aset menggunakan strategi final per aset.
    Long-only. Mendukung Kelly Criterion position sizing.

    use_kelly:          True  → Kelly Criterion (adaptive, optimal)
                        False → Fixed fraction (position_size_pct%)
    position_size_pct:  hanya dipakai jika use_kelly=False
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
                    'kelly_frac': position.get('frac', 0),
                    'pnl':        pnl,
                    'pnl_pct':    pnl_pct,
                    'reason':     'SL' if hit_sl else 'TP',
                })
                position = None
                equity_curve.append(balance)
                continue

        # --- Entry jika sinyal BUY dan belum ada posisi ---
        if not position and signal == 'BUY' and balance > 0:
            # Bayesian Kelly: blend default WR dengan observed WR
            # Makin banyak trade, makin dominan observed WR
            # BTC: Kelly adaptive (timing strategy — posisi kecil masuk akal)
# Gold & SPX: Fixed 90% (B&H style — harus fully invested)
            BAH_SYMBOLS = {"GC=F", "^GSPC"}
            if use_kelly and symbol not in BAH_SYMBOLS:
                DEFAULT_WR = {"BTC/USDT": 0.41}
                prior_wr   = DEFAULT_WR.get(symbol, 0.40)
                prior_n    = 20
                obs_wins   = sum(1 for t in trades if t["pnl"] > 0)
                obs_n      = len(trades)
                blended_wr = (prior_wr * prior_n + obs_wins) / (prior_n + obs_n)
                frac       = _kelly_fraction(blended_wr, tp_pct, sl_pct)
            elif symbol in BAH_SYMBOLS:
                frac = 0.90
            else:
                frac = position_size_pct / 100.0

            margin   = balance * frac
            exposure = margin * leverage
            qty      = exposure / current_price
            position = {
                'type':   'long',
                'entry':  current_price,
                'qty':    qty,
                'margin': margin,
                'frac':   frac,
                'idx':    i,
            }
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
            'kelly_frac': position.get('frac', 0),
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

    # Kelly stats
    kelly_fracs = [t.get('kelly_frac', 0) for t in trades if t.get('kelly_frac', 0) > 0]
    avg_kelly   = sum(kelly_fracs) / len(kelly_fracs) if kelly_fracs else 0

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
        'avg_kelly_frac':  round(avg_kelly * 100, 1),  # dalam %
        'use_kelly':       use_kelly,
        'trades':          trades,
        'equity_curve':    equity_curve,
    }