import json
import os
from datetime import datetime, timedelta

# Lokasi file log
PAPER_FILE = "logs/paper_trades.json"
PARAMS_FILE = "logs/current_params.json"
SUGGESTIONS_FILE = "logs/self_improvement_suggestions.json"

def load_current_params():
    """Muat parameter trading saat ini dari file (atau default)."""
    default = {
        'kelly_mult': 0.5,
        'trailing_stop_pct': 0.2,
        'rsi_lo': 45,
        'rsi_hi': 65,
        'delta_lookback': 3
    }
    if os.path.exists(PARAMS_FILE):
        with open(PARAMS_FILE, 'r') as f:
            params = json.load(f)
            # gabungkan dengan default jika ada yang hilang
            default.update(params)
    return default

def save_current_params(params):
    """Simpan parameter trading saat ini ke file."""
    with open(PARAMS_FILE, 'w') as f:
        json.dump(params, f, indent=2)

def get_last_week_trades():
    """Ambil semua closed trade dalam 7 hari terakhir."""
    if not os.path.exists(PAPER_FILE):
        return []
    with open(PAPER_FILE, 'r') as f:
        data = json.load(f)
    trades = data.get('trades', [])
    one_week_ago = datetime.now() - timedelta(days=7)
    return [t for t in trades if datetime.fromisoformat(t.get('exit_time', '')) > one_week_ago]

def evaluate_performance(trades):
    """Hitung metrik sederhana dari daftar trade."""
    if not trades:
        return {
            'win_rate': 0,
            'total_pnl': 0,
            'n_trades': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0
        }
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    win_rate = len(wins) / len(trades)
    total_pnl = sum(t['pnl'] for t in trades)
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    profit_factor = sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses)) if losses else 0
    return {
        'win_rate': round(win_rate, 3),
        'total_pnl': round(total_pnl, 2),
        'n_trades': len(trades),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2)
    }

def suggest_parameters(performance, current_params):
    """Berdasarkan performa, usulkan perubahan parameter."""
    suggestions = {}
    # Aturan untuk kelly multiplier
    if performance['n_trades'] >= 5:
        if performance['win_rate'] < 0.4:
            # Turunkan risk
            suggestions['kelly_mult'] = max(0.3, current_params.get('kelly_mult', 0.5) - 0.1)
        elif performance['win_rate'] > 0.6:
            # Naikkan risk sedikit
            suggestions['kelly_mult'] = min(0.8, current_params.get('kelly_mult', 0.5) + 0.05)

    # Aturan untuk trailing stop
    if performance['n_trades'] >= 5 and performance['avg_loss'] < -10:
        # Perketat stop jika loss rata-rata besar
        suggestions['trailing_stop_pct'] = max(0.12, current_params.get('trailing_stop_pct', 0.2) - 0.02)

    # Aturan untuk RSI threshold (contoh sederhana)
    if performance['n_trades'] >= 10 and performance['win_rate'] < 0.4:
        # Jika win rate rendah, coba sesuaikan rentang RSI (misal: geser ke bawah)
        suggestions['rsi_lo'] = max(30, current_params.get('rsi_lo', 45) - 5)
        suggestions['rsi_hi'] = min(70, current_params.get('rsi_hi', 65) - 5)

    return suggestions

def backtest_suggestion(current_params, suggestion, trades=None):
    """Backtest saran perubahan parameter."""
    # Simulasi sederhana: kita bisa bandingkan dengan baseline
    # Untuk sekarang, kita asumsikan saran selalu diterima jika memiliki data minimal.
    # Nanti bisa diperbaiki dengan panggilan ke backtest.py yang sudah ada.
    print(f"  Backtesting suggestion: {suggestion}")
    # TODO: implementasi backtest nyata menggunakan data historis
    return True  # dummy

def log_suggestion(suggestions, accepted=False):
    """Simpan saran ke file log."""
    os.makedirs(os.path.dirname(SUGGESTIONS_FILE), exist_ok=True)
    history = []
    if os.path.exists(SUGGESTIONS_FILE):
        with open(SUGGESTIONS_FILE, 'r') as f:
            history = json.load(f)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "suggestions": suggestions,
        "accepted": accepted
    }
    history.append(entry)
    # Simpan maksimal 100 entri
    if len(history) > 100:
        history = history[-100:]
    with open(SUGGESTIONS_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def apply_suggestion(suggestions):
    """Terapkan saran ke parameter dan simpan ke file."""
    params = load_current_params()
    params.update(suggestions)
    save_current_params(params)
    print(f"  Applied suggestions: {suggestions}")

def run_weekly_improvement():
    """Fungsi utama untuk dijalankan setiap minggu."""
    print("=== Running Self-Improvement Loop ===")
    trades = get_last_week_trades()
    print(f"Trades last week: {len(trades)}")
    perf = evaluate_performance(trades)
    print(f"Performance: {perf}")

    current_params = load_current_params()
    suggestions = suggest_parameters(perf, current_params)
    if suggestions:
        print(f"Suggestions: {suggestions}")
        accepted = {}
        for param, value in suggestions.items():
            if backtest_suggestion(current_params, {param: value}, trades):
                accepted[param] = value
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