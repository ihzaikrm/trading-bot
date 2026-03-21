# core/command_handler.py
import json
import os
from datetime import datetime
from .notifier import send_message
from .llm_performance import load_performance
from .signal_engine import get_strategy_status_text

def handle_commands(data, chat_id):
    last_id_file = "logs/last_update_id.txt"
    last_update_id = 0
    if os.path.exists(last_id_file):
        with open(last_id_file, "r") as f:
            last_update_id = int(f.read().strip())

    from .notifier import get_updates
    updates = get_updates(offset=last_update_id+1)
    if not updates:
        return

    max_id = max(u["update_id"] for u in updates)
    with open(last_id_file, "w") as f:
        f.write(str(max_id))

    for update in updates:
        if "message" not in update:
            continue
        msg = update["message"]
        chat = msg["chat"]["id"]
        if str(chat) != chat_id and chat_id != "*":
            continue
        text = msg.get("text", "").strip()
        if not text.startswith("/"):
            continue

        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:]

        response = None
        if cmd == "/status":
            response = format_status(data)
        elif cmd == "/trades":
            response = format_trades(data)
        elif cmd == "/positions":
            response = format_positions(data)
        elif cmd == "/perf":
            response = format_perf()
        elif cmd == "/config":
            response = format_config(args)
        elif cmd == "/strategy":
            response = get_strategy_status_text()
        elif cmd == "/pause":
            response = pause_bot(data)
        elif cmd == "/resume":
            response = resume_bot(data)
        elif cmd == "/help":
            response = help_message()
        else:
            response = f"Unknown command: {cmd}\nType /help for list."

        if response:
            send_message(chat, response)

def format_status(data):
    balance = data.get("balance", 0)
    positions = data.get("positions", {})
    shorts = data.get("shorts", {})
    trades = data.get("trades", [])
    today = datetime.now().strftime("%Y-%m-%d")
    today_pnl = sum(t.get("pnl", 0) for t in trades if t.get("exit_time", "").startswith(today))
    lines = [
        "📊 *STATUS BOT*",
        f"Balance: ${balance:.2f}",
        f"Today PnL: ${today_pnl:.2f}",
        f"Long: {', '.join(positions.keys()) if positions else 'Tidak ada'}",
        f"Short: {', '.join(shorts.keys()) if shorts else 'Tidak ada'}",
    ]
    return "\n".join(lines)

def format_trades(data):
    trades = data.get("trades", [])
    if not trades:
        return "Belum ada trade."
    lines = ["📈 *10 TRADE TERAKHIR*"]
    for t in trades[-10:]:
        pnl = t.get("pnl", 0)
        emoji = "✅" if pnl > 0 else "🔴"
        strategy = t.get("strategy", "unknown")
        lines.append(f"{emoji} {t.get('asset')} {t.get('type')} PnL ${pnl:.2f} ({strategy})")
    return "\n".join(lines)

def format_positions(data):
    positions = data.get("positions", {})
    shorts = data.get("shorts", {})
    lines = ["📌 *POSISI TERBUKA*"]
    for sym, pos in positions.items():
        lines.append(f"Long {sym}: Entry ${pos['entry_price']:.2f}, Qty {pos['qty']:.4f}")
    for sym, pos in shorts.items():
        lines.append(f"Short {sym}: Entry ${pos['entry_price']:.2f}, Qty {pos['qty']:.4f}")
    if not positions and not shorts:
        lines.append("Tidak ada posisi terbuka.")
    return "\n".join(lines)

def format_perf():
    perf = load_performance()
    lines = ["🤖 *LLM PERFORMANCE*"]
    for llm, stats in perf.items():
        acc = stats.get('accuracy', 0) * 100
        lines.append(f"{llm}: {stats.get('correct',0)}/{stats.get('total',0)} ({acc:.1f}%)")
    return "\n".join(lines)

def format_config(args):
    from config.trading_params import STOP_LOSS_PCT, TAKE_PROFIT_PCT, LEVERAGE
    lines = [
        "⚙️ *KONFIGURASI*",
        f"Stop Loss: {STOP_LOSS_PCT}%",
        f"Take Profit: {TAKE_PROFIT_PCT}%",
        f"Leverage: {LEVERAGE}x",
    ]
    return "\n".join(lines)

def pause_bot(data):
    with open("logs/pause.txt", "w") as f:
        f.write("paused")
    return "⏸️ Bot di-pause. Untuk resume, kirim /resume."

def resume_bot(data):
    if os.path.exists("logs/pause.txt"):
        os.remove("logs/pause.txt")
        return "▶️ Bot di-resume."
    return "Bot sudah dalam keadaan aktif."

def help_message():
    return """
*Telegram Commands*
/status - Tampilkan status bot
/trades - 10 trade terakhir
/positions - Detail posisi terbuka
/perf - Performa LLM
/config - Tampilkan konfigurasi
/strategy - Tampilkan strategi per aset
/pause - Pause trading
/resume - Resume trading
/help - Pesan ini
"""