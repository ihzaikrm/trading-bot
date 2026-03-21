import os
# core/risk_manager.py
from datetime import datetime

def force_close_position(data, symbol, current_price, reason):
    positions = data.get("positions", {})
    shorts = data.get("shorts", {})

    if symbol in positions:
        pos = positions[symbol]
        entry = pos["entry_price"]
        qty = pos["qty"]
        pnl = (current_price - entry) * qty
        pos_type = "long"
        data["balance"] += pos["amount"] + pnl
        data["trades"].append({
            "asset": symbol,
            "type": pos_type,
            "entry_price": entry,
            "exit_price": current_price,
            "qty": qty,
            "amount": pos["amount"],
            "pnl": round(pnl, 2),
            "reason": reason,
            "time": pos["time"],
            "exit_time": datetime.now().isoformat()
        })
        del positions[symbol]
        print(f"[FORCE CLOSE] {symbol} long ditutup karena {reason}. PnL: {pnl:.2f}")

    elif symbol in shorts:
        pos = shorts[symbol]
        entry = pos["entry_price"]
        qty = pos["qty"]
        pnl = (entry - current_price) * qty
        pos_type = "short"
        data["balance"] += pos["amount"] + pnl
        data["trades"].append({
            "asset": symbol,
            "type": pos_type,
            "entry_price": entry,
            "exit_price": current_price,
            "qty": qty,
            "amount": pos["amount"],
            "pnl": round(pnl, 2),
            "reason": reason,
            "time": pos["time"],
            "exit_time": datetime.now().isoformat()
        })
        del shorts[symbol]
        print(f"[FORCE CLOSE] {symbol} short ditutup karena {reason}. PnL: {pnl:.2f}")

    data["positions"] = positions
    data["shorts"] = shorts
    return data

# â”€â”€ B4: Cooldown setelah SL hit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import json as _json
from datetime import datetime as _dt, timezone as _tz, timedelta as _td

_COOLDOWN_FILE  = os.path.join(os.path.dirname(__file__), "..", "logs", "paper_trades.json")
COOLDOWN_CYCLES = 3   # skip 3 siklus
CYCLE_MINUTES   = 60  # 1 siklus = 1 jam


def _load_trades_cd():
    try:
        with open(_COOLDOWN_FILE, "r", encoding="utf-8") as f:
            return _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError):
        return {}


def _save_trades_cd(data):
    os.makedirs(os.path.dirname(_COOLDOWN_FILE), exist_ok=True)
    with open(_COOLDOWN_FILE, "w", encoding="utf-8") as f:
        _json.dump(data, f, indent=2, default=str)


def set_cooldown(asset):
    """Panggil saat SL hit. Blokir aset selama COOLDOWN_CYCLES jam."""
    data = _load_trades_cd()
    if "cooldown" not in data:
        data["cooldown"] = {}
    until = _dt.now(_tz.utc) + _td(minutes=COOLDOWN_CYCLES * CYCLE_MINUTES)
    data["cooldown"][asset] = until.isoformat()
    _save_trades_cd(data)
    logger.info("[B4] Cooldown aktif: %s hingga %s", asset, until.strftime("%Y-%m-%d %H:%M UTC"))


def is_in_cooldown(asset):
    """Return True jika aset masih cooldown. Panggil di bot.py sebelum open posisi."""
    data = _load_trades_cd()
    cooldown_map = data.get("cooldown", {})
    if asset not in cooldown_map:
        return False
    try:
        until = _dt.fromisoformat(cooldown_map[asset])
        if until.tzinfo is None:
            until = until.replace(tzinfo=_tz.utc)
        now = _dt.now(_tz.utc)
        if now < until:
            remaining = int((until - now).total_seconds() / 60)
            logger.info("[B4] %s cooldown â€” %d menit tersisa", asset, remaining)
            return True
        del cooldown_map[asset]
        data["cooldown"] = cooldown_map
        _save_trades_cd(data)
        return False
    except (ValueError, KeyError):
        return False
