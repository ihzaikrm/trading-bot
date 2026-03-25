import json
import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.logger import setup_logger

logger = setup_logger("performance_tracker")

def load_trades(filepath="data/paper_trades.json"):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data.get("trades", [])

def compute_metrics(trades):
    if not trades:
        return {
            "n_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "sharpe": None
        }
    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) <= 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    total_pnl = sum(t.get("pnl", 0) for t in trades)
    avg_win = sum(t.get("pnl", 0) for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.get("pnl", 0) for t in losses) / len(losses) if losses else 0
    profit_factor = abs(sum(t.get("pnl", 0) for t in wins) / sum(t.get("pnl", 0) for t in losses)) if losses else 0

    # Simplified max drawdown based on cumulative PnL
    cum = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cum += t.get("pnl", 0)
        if cum > peak:
            peak = cum
        dd = (peak - cum) / peak if peak != 0 else 0
        if dd > max_dd:
            max_dd = dd
    max_dd *= 100

    return {
        "n_trades": len(trades),
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe": None  # Placeholder
    }

def update_performance_report():
    trades = load_trades()
    metrics = compute_metrics(trades)
    report_file = "data/performance_report.json"
    with open(report_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "last_trades": trades[-10:] if trades else []
        }, f, indent=2)
    logger.info(f"Performance report saved: {metrics['n_trades']} trades, WR={metrics['win_rate']}%")
    return metrics

if __name__ == "__main__":
    update_performance_report()
