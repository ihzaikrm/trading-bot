import json
import pandas as pd
from datetime import datetime, timedelta

def get_last_week_trades():
    """Ambil semua closed trade dalam 7 hari terakhir."""
    try:
        with open('logs/paper_trades.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    trades = data.get('trades', [])
    one_week_ago = datetime.now() - timedelta(days=7)
    return [t for t in trades if datetime.fromisoformat(t.get('exit_time', '')) > one_week_ago]

def evaluate_performance(trades):
    """Hitung metrik sederhana dari daftar trade."""
    if not trades:
        return {'win_rate': 0, 'total_pnl': 0, 'n_trades': 0, 'avg_win': 0, 'avg_loss': 0}
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    win_rate = len(wins) / len(trades)
    total_pnl = sum(t['pnl'] for t in trades)
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    return {
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'n_trades': len(trades),
        'avg_win': avg_win,
        'avg_loss': avg_loss
    }

def suggest_parameters(performance, current_params):
    """Berdasarkan performa, usulkan perubahan parameter."""
    suggestions = {}
    # Contoh aturan sederhana (bisa diganti dengan panggilan LLM nanti)
    if performance['win_rate'] < 0.4 and performance['n_trades'] >= 5:
        # Jika win rate rendah, turunkan kelly_mult
        suggestions['kelly_mult'] = max(0.3, current_params.get('kelly_mult', 0.5) - 0.1)
    elif performance['win_rate'] > 0.6 and performance['n_trades'] >= 5:
        # Jika win rate tinggi, naikkan kelly_mult sedikit
        suggestions['kelly_mult'] = min(0.8, current_params.get('kelly_mult', 0.5) + 0.05)

    # Contoh untuk trailing stop
    if performance['avg_loss'] < -10 and performance['n_trades'] >= 5:
        # Jika loss rata-rata besar, perketat trailing stop
        suggestions['trailing_stop_pct'] = max(0.12, current_params.get('trailing_stop_pct', 0.2) - 0.02)
    return suggestions

def run_weekly_improvement():
    print("=== Running Self-Improvement Loop ===")
    trades = get_last_week_trades()
    print(f"Trades last week: {len(trades)}")
    perf = evaluate_performance(trades)
    print(f"Performance: {perf}")

    # Load current parameters (misal dari config/trading_params.py)
    # Untuk sementara kita hardcode
    current_params = {
        'kelly_mult': 0.5,
        'trailing_stop_pct': 0.2,
        'rsi_lo': 45,
        'rsi_hi': 65
    }
    suggestions = suggest_parameters(perf, current_params)
    if suggestions:
        print(f"Suggestions: {suggestions}")
        # TODO: backtest suggestions before applying
    else:
        print("No suggestions.")

if __name__ == '__main__':
    run_weekly_improvement()
