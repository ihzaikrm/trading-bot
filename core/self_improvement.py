import json
import os
import sys
from datetime import datetime, timedelta

# Tambahkan path proyek agar bisa import modul lain
sys.path.insert(0, os.getcwd())

# Import backtest dari file backtest.py (asumsi ada fungsi run_backtest_strategy)
try:
    from backtest import run_backtest_strategy  # kita akan buat nanti
except ImportError:
    # Jika belum ada, buat fungsi dummy
    def run_backtest_strategy(params):
        # Dummy: return return pct, win_rate, max_dd
        print("  (dummy backtest) using params:", params)
        return 0.10, 0.5, 0.10
    print("[WARN] backtest.run_backtest_strategy not found, using dummy")

# Konfigurasi
PARAMS_FILE = "logs/current_params.json"
SUGGESTIONS_LOG = "logs/self_improvement_suggestions.json"

def load_current_params():
    """Load current parameters from file or default."""
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
            # Merge dengan default untuk memastikan semua key ada
            default.update(params)
    return default

def get_last_week_trades():
    """Ambil semua closed trade dalam 7 hari terakhir."""
    try:
        with open('logs/paper_trades.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    trades = data.get('trades', [])
    one_week_ago = datetime.now() - timedelta(days=7)
    # Filter trades yang memiliki exit_time dan terjadi dalam seminggu
    return [t for t in trades if 'exit_time' in t and datetime.fromisoformat(t['exit_time']) > one_week_ago]

def evaluate_performance(trades):
    """Hitung metrik performa dari daftar trade."""
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
    profit_factor = (sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses))) if losses else float('inf')
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
    # Aturan kelly multiplier
    if performance['n_trades'] >= 5:
        if performance['win_rate'] < 0.4:
            suggestions['kelly_mult'] = max(0.3, current_params.get('kelly_mult', 0.5) - 0.1)
        elif performance['win_rate'] > 0.6:
            suggestions['kelly_mult'] = min(0.8, current_params.get('kelly_mult', 0.5) + 0.05)
    # Aturan trailing stop
    if performance['n_trades'] >= 5 and performance['avg_loss'] < -10:
        suggestions['trailing_stop_pct'] = max(0.12, current_params.get('trailing_stop_pct', 0.2) - 0.02)
    # Aturan RSI threshold
    if performance['n_trades'] >= 10:
        # Contoh: jika win rate rendah, mungkin perlu adjust RSI
        if performance['win_rate'] < 0.4:
            # Coba lebih konservatif
            suggestions['rsi_lo'] = current_params.get('rsi_lo', 45) + 2
            suggestions['rsi_hi'] = current_params.get('rsi_hi', 65) - 2
    return suggestions

def backtest_suggestion(current_params, suggestion):
    """Backtest perubahan parameter menggunakan data historis."""
    # Gabungkan parameter baru dengan current
    test_params = current_params.copy()
    test_params.update(suggestion)
    # Panggil fungsi backtest (misal dari backtest.py)
    # Kita asumsikan ada fungsi run_backtest_strategy yang mengembalikan (return_pct, win_rate, max_dd)
    ret, wr, dd = run_backtest_strategy(test_params)
    # Bandingkan dengan baseline
    baseline_ret, baseline_wr, baseline_dd = run_backtest_strategy(current_params)
    # Jika return lebih baik dan drawdown tidak lebih buruk, atau win rate naik signifikan
    if ret > baseline_ret * 1.05 and dd <= baseline_dd * 1.1:
        return True
    return False

def log_suggestion(suggestions, accepted=False):
    """Simpan saran ke file log."""
    os.makedirs(os.path.dirname(SUGGESTIONS_LOG), exist_ok=True)
    if os.path.exists(SUGGESTIONS_LOG):
        with open(SUGGESTIONS_LOG, 'r') as f:
            history = json.load(f)
    else:
        history = []
    entry = {
        "timestamp": datetime.now().isoformat(),
        "suggestions": suggestions,
        "accepted": accepted
    }
    history.append(entry)
    with open(SUGGESTIONS_LOG, 'w') as f:
        json.dump(history, f, indent=2)

def apply_suggestion(suggestions):
    """Terapkan saran ke file konfigurasi."""
    params = load_current_params()
    params.update(suggestions)
    with open(PARAMS_FILE, 'w') as f:
        json.dump(params, f, indent=2)
    print("  Parameters updated in", PARAMS_FILE)

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
            # Uji perubahan satu per satu
            test_suggestion = {param: value}
            if backtest_suggestion(current_params, test_suggestion):
                accepted[param] = value
                print(f"  ✓ {param} -> {value} accepted (backtest passed)")
            else:
                print(f"  ✗ {param} -> {value} rejected (backtest failed)")
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
