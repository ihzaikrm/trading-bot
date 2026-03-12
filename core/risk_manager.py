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