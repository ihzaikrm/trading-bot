import json
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Tambah path agar bisa import backtest
sys.path.insert(0, os.getcwd())

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
        return {'win_rate': 0, 'total_pnl': 0, 'n_trades': 0, 'avg_win': 0, 'avg_loss': 0, 'profit_factor': 0}
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    win_rate = len(wins) / len(trades)
    total_pnl = sum(t['pnl'] for t in trades)
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    profit_factor = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses else 0
    return {
        'win_rate': round(win_rate, 3),
        'total_pnl': round(total_pnl, 2),
        'n_trades': len(trades),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2)
    }

def load_current_params():
    """Muat parameter saat ini dari file konfigurasi atau default."""
    # Coba import dari config (jika ada) atau gunakan default
    try:
        from config.trading_params import PARAMS
        return PARAMS
    except ImportError:
        return {
            'kelly_mult': 0.5,
            'trailing_stop_pct': 0.2,
            'rsi_lo': 45,
            'rsi_hi': 65,
            'delta_lookback': 3
        }

def backtest_suggestion(current_params, suggestion):
    """Backtest perubahan parameter menggunakan data historis."""
    from backtest import run_backtest_strategy

    # Buat parameter sementara
    test_params = current_params.copy()
    for k, v in suggestion.items():
        test_params[k] = v

    # Konversi ke format yang diharapkan backtest
    rsi_lo = test_params.get('rsi_lo', 45)
    rsi_hi = test_params.get('rsi_hi', 65)
    trail_pct = test_params.get('trailing_stop_pct', 0.2)
    delta_lookback = test_params.get('delta_lookback', 3)

    result = run_backtest_strategy(rsi_lo, rsi_hi, trail_pct, delta_lookback)
    # Bandingkan dengan baseline
    baseline = run_backtest_strategy()  # default parameter
    return result['return_pct'] > baseline['return_pct']

def log_suggestion(suggestions, accepted=False):
    """Simpan saran ke file log."""
    log_file = "logs/self_improvement_suggestions.json"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    try:
        with open(log_file, 'r') as f:
            history = json.load(f)
    except:
        history = []
    entry = {
        "timestamp": datetime.now().isoformat(),
        "suggestions": suggestions,
        "accepted": accepted
    }
    history.append(entry)
    with open(log_file, 'w') as f:
        json.dump(history, f, indent=2)

def suggest_parameters(performance, current_params):
    """Berdasarkan performa, usulkan perubahan parameter."""
    suggestions = {}
    # Aturan sederhana untuk kelly multiplier
    if performance['n_trades'] >= 5:
        if performance['win_rate'] < 0.4:
            # Jika win rate rendah, turunkan kelly
            suggestions['kelly_mult'] = max(0.3, current_params.get('kelly_mult', 0.5) - 0.1)
        elif performance['win_rate'] > 0.6:
            # Jika win rate tinggi, naikkan kelly
            suggestions['kelly_mult'] = min(0.8, current_params.get('kelly_mult', 0.5) + 0.05)

    # Aturan untuk trailing stop berdasarkan avg loss
    if performance['n_trades'] >= 5 and performance['avg_loss'] < -10:
        # Perketat trailing stop jika loss rata-rata besar
        suggestions['trailing_stop_pct'] = max(0.12, current_params.get('trailing_stop_pct', 0.2) - 0.02)

    # Aturan untuk RSI threshold (contoh sederhana)
    # if performance['n_trades'] >= 10 and performance['win_rate'] < 0.4:
    #     suggestions['rsi_lo'] = max(40, current_params.get('rsi_lo', 45) - 2)
    #     suggestions['rsi_hi'] = min(70, current_params.get('rsi_hi', 65) + 2)

    return suggestions

def apply_suggestion(suggestions):
    """Terapkan saran ke file logs/current_params.json."""
    params = load_current_params()
    params.update(suggestions)
    with open('logs/current_params.json', 'w') as f:
        json.dump(params, f, indent=2)
    print("Parameters updated in logs/current_params.json")

def run_weekly_improvement():
    print("=== Running Self-Improvement Loop ===")
    trades = get_last_week_trades()
    print(f"Trades last week: {len(trades)}")
    perf = evaluate_performance(trades)
    print(f"Performance: {perf}")

    current_params = load_current_params()
    print(f"Current params: {current_params}")

    suggestions = suggest_parameters(perf, current_params)
    if suggestions:
        print(f"Suggestions: {suggestions}")
        # Backtest setiap saran
        accepted = {}
        for param, value in suggestions.items():
            # Buat saran tunggal untuk diuji
            single_suggestion = {param: value}
            if backtest_suggestion(current_params, single_suggestion):
                accepted[param] = value
                print(f"  Accepted {param} = {value}")
            else:
                print(f"  Rejected {param} = {value} (backtest not better)")
        if accepted:
            print(f"Accepted suggestions after backtest: {accepted}")
            apply_suggestion(accepted)
            log_suggestion(accepted, accepted=True)
        else:
            print("No suggestions accepted after backtest.")
            log_suggestion(suggestions, accepted=False)
    else:
        print("No suggestions.")

if __name__ == '__main__':
    run_weekly_improvement()
