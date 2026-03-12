# core/daily_report.py
import json
import os
from datetime import datetime, timedelta
from .notifier import tg

REPORT_FILE = "logs/last_report.txt"
PAPER_FILE = "logs/paper_trades.json"

def should_send_report():
    """Cek apakah sudah waktunya kirim laporan (jam 00:00 UTC)"""
    now = datetime.utcnow()
    # Kirim jika jam 00:00 - 00:05, dan belum pernah kirim hari ini
    if now.hour == 0 and now.minute < 5:
        if os.path.exists(REPORT_FILE):
            with open(REPORT_FILE, "r") as f:
                last = f.read().strip()
            if last == now.strftime("%Y-%m-%d"):
                return False
        return True
    return False

def mark_report_sent():
    """Tandai laporan sudah dikirim hari ini"""
    with open(REPORT_FILE, "w") as f:
        f.write(datetime.utcnow().strftime("%Y-%m-%d"))

def load_trades():
    if os.path.exists(PAPER_FILE):
        with open(PAPER_FILE) as f:
            return json.load(f)
    return {"balance": 1000.0, "trades": [], "positions": {}, "shorts": {}}

def generate_daily_report():
    """Buat teks laporan harian"""
    data = load_trades()
    trades = data.get("trades", [])
    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Filter trade kemarin (sebenarnya hari sebelumnya, karena jam 00:00 laporan kemarin)
    daily_trades = [t for t in trades if t.get("exit_time", "").startswith(yesterday)]
    daily_pnl = sum(t.get("pnl", 0) for t in daily_trades)
    daily_wins = sum(1 for t in daily_trades if t.get("pnl", 0) > 0)
    daily_losses = sum(1 for t in daily_trades if t.get("pnl", 0) < 0)
    daily_count = len(daily_trades)

    balance = data.get("balance", 0)
    positions = data.get("positions", {})
    shorts = data.get("shorts", {})

    lines = [
        f"📆 *DAILY REPORT {yesterday}*",
        f"Trades: {daily_count} ({daily_wins} profit, {daily_losses} loss)",
        f"PnL: ${daily_pnl:.2f}",
        f"Balance: ${balance:.2f}",
        f"Open Long: {', '.join(positions.keys()) if positions else 'Tidak ada'}",
        f"Open Short: {', '.join(shorts.keys()) if shorts else 'Tidak ada'}",
    ]
    if daily_trades:
        lines.append("\n*Detail Trade:*")
        for t in daily_trades[-5:]:  # maks 5 trade
            emoji = "✅" if t.get("pnl", 0) > 0 else "🔴"
            lines.append(f"{emoji} {t.get('asset')} {t.get('type')} PnL ${t.get('pnl',0):.2f}")
    return "\n".join(lines)

def send_daily_report():
    """Kirim laporan jika waktunya"""
    if should_send_report():
        report = generate_daily_report()
        tg(report)
        mark_report_sent()
        print("[Daily Report] Sent.")