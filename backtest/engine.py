# backtest/engine.py
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.indicators import calc_indicators

def rule_based_signal(ind):
    """
    Strategi sederhana berdasarkan indikator (tanpa LLM)
    """
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
    elif score <= -3: return "SELL"
    return "HOLD"

def backtest(symbol, asset_type, start_date, end_date,
             sl_pct=2.0, tp_pct=5.0, leverage=1,
             initial_balance=1000.0):
    """
    Jalankan backtest untuk satu aset
    """
    from .data_loader import load_data

    # Ambil data harian
    df = load_data(asset_type, symbol, start_date, end_date, timeframe='1d')
    if df is None or len(df) < 50:
        return None

    closes = df['close'].tolist()
    balance = initial_balance
    position = None  # {'type':'long'/'short', 'entry':price, 'qty':float}
    trades = []
    equity_curve = [balance]

    for i in range(50, len(closes)):  # butuh data untuk indikator
        current_price = closes[i]
        # Hitung indikator dari data hingga i
        ind = calc_indicators(closes[:i+1])
        if ind is None:
            continue
        signal = rule_based_signal(ind)

        # Cek SL/TP jika ada posisi
        if position:
            if position['type'] == 'long':
                pnl_pct = (current_price - position['entry']) / position['entry'] * 100 * leverage
            else:  # short
                pnl_pct = (position['entry'] - current_price) / position['entry'] * 100 * leverage

            if pnl_pct <= -sl_pct or pnl_pct >= tp_pct:
                # Tutup posisi
                exit_price = current_price
                if position['type'] == 'long':
                    pnl = (exit_price - position['entry']) * position['qty']
                else:
                    pnl = (position['entry'] - exit_price) * position['qty']
                balance += position['amount'] + pnl
                trades.append({
                    'entry_date': df.index[position['idx']],
                    'exit_date': df.index[i],
                    'type': position['type'],
                    'entry': position['entry'],
                    'exit': exit_price,
                    'qty': position['qty'],
                    'pnl': pnl,
                    'reason': 'SL/TP'
                })
                position = None
                equity_curve.append(balance)
                continue

        # Jika tidak ada posisi, cek sinyal entry
        if not position:
            if signal == 'BUY':
                qty = (balance * leverage) / current_price
                position = {
                    'type': 'long',
                    'entry': current_price,
                    'qty': qty,
                    'amount': balance,  # modal yang digunakan (tanpa leverage)
                    'idx': i
                }
                balance = 0  # semua modal digunakan
            elif signal == 'SELL':  # short
                qty = (balance * leverage) / current_price
                position = {
                    'type': 'short',
                    'entry': current_price,
                    'qty': qty,
                    'amount': balance,
                    'idx': i
                }
                balance = 0

    # Tutup posisi di akhir jika masih ada
    if position:
        exit_price = closes[-1]
        if position['type'] == 'long':
            pnl = (exit_price - position['entry']) * position['qty']
        else:
            pnl = (position['entry'] - exit_price) * position['qty']
        balance += position['amount'] + pnl
        trades.append({
            'entry_date': df.index[position['idx']],
            'exit_date': df.index[-1],
            'type': position['type'],
            'entry': position['entry'],
            'exit': exit_price,
            'qty': position['qty'],
            'pnl': pnl,
            'reason': 'End of data'
        })
        equity_curve.append(balance)

    return {
        'symbol': symbol,
        'start': start_date,
        'end': end_date,
        'initial_balance': initial_balance,
        'final_balance': balance,
        'total_return': (balance - initial_balance) / initial_balance * 100,
        'trades': trades,
        'equity_curve': equity_curve
    }