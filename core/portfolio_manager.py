"""
core/portfolio_manager.py
Sprint 4: Portfolio Allocator + Partial TP + Rotation Engine
"""
import json, os
from datetime import datetime

PORTFOLIO_FILE = "logs/portfolio_state.json"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE) as f:
            return json.load(f)
    return {"positions": {}, "history": [], "last_rotation": None}

def save_portfolio(state):
    os.makedirs("logs", exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)

def alloc_per_asset(narrative_state, balance, max_positions=5):
    """
    Hitung alokasi per aset berdasarkan narasi aktif.
    Return: dict {symbol: amount}
    """
    selected = narrative_state.get("selected_assets", [])
    allocation = narrative_state.get("allocation", {
        "crypto": 35, "stocks": 35, "commodities": 15, "cash": 15
    })

    if not selected:
        return {}

    # Hitung cash yang tersedia (exclude cash allocation)
    cash_pct = allocation.get("cash", 15) / 100
    investable = balance * (1 - cash_pct)

    # Kelompokkan per kategori
    by_category = {}
    for a in selected[:max_positions]:
        cat = a.get("category", "stocks")
        if cat == "cash_pct":
            continue
        by_category.setdefault(cat, []).append(a)

    # Alokasi per kategori lalu per aset
    result = {}
    for cat, assets in by_category.items():
        cat_pct = allocation.get(cat, 20) / 100
        # Normalisasi agar total tidak melebihi investable
        total_cat_pct = sum(allocation.get(c, 20) / 100 for c in by_category)
        normalized = cat_pct / total_cat_pct if total_cat_pct > 0 else cat_pct
        cat_amount = investable * normalized
        per_asset = cat_amount / len(assets)
        for a in assets:
            result[a["symbol"]] = {
                "amount": round(per_asset, 2),
                "narrative": a["narrative"],
                "category": cat,
                "tp_pct": a["tp_pct"],
                "sl_pct": a["sl_pct"],
            }
    return result

def check_partial_tp(symbol, entry_price, current_price, qty, tp_pct):
    """
    Partial TP logic:
    +30% dari TP target → jual 50% posisi
    +60% dari TP target → jual 25% lagi
    Return: (action, qty_to_sell, reason)
    """
    if entry_price <= 0:
        return None, 0, ""

    pnl_pct = (current_price - entry_price) / entry_price * 100
    tp_30 = tp_pct * 0.30  # 30% dari target TP
    tp_60 = tp_pct * 0.60  # 60% dari target TP

    if pnl_pct >= tp_pct:
        return "FULL_TP", qty, f"Full TP hit ({pnl_pct:.1f}%)"
    elif pnl_pct >= tp_60:
        return "PARTIAL_TP_2", qty * 0.25, f"Partial TP 2 ({pnl_pct:.1f}% >= {tp_60:.1f}%)"
    elif pnl_pct >= tp_30:
        return "PARTIAL_TP_1", qty * 0.50, f"Partial TP 1 ({pnl_pct:.1f}% >= {tp_30:.1f}%)"
    return None, 0, ""

def check_rotation_needed(narrative_state, positions):
    """
    Cek apakah perlu rotasi posisi berdasarkan narasi baru.
    Return: list simbol yang perlu di-close untuk rotasi
    """
    if not positions:
        return []

    active_narratives = [n for n, _ in narrative_state.get("active_narratives", [])]
    rotation_urgency = narrative_state.get("rotation_urgency", "low")
    selected_symbols = [a["symbol"] for a in narrative_state.get("selected_assets", [])]

    to_close = []
    for symbol, pos in positions.items():
        pos_narrative = pos.get("narrative", "")
        # Close jika narasi posisi tidak lagi aktif DAN urgency medium/high
        if pos_narrative not in active_narratives and rotation_urgency in ["medium", "high"]:
            to_close.append((symbol, f"Narasi {pos_narrative} tidak aktif, urgency={rotation_urgency}"))
        # Close jika simbol tidak ada di selected list baru (rotasi penuh)
        elif rotation_urgency == "high" and symbol not in selected_symbols:
            to_close.append((symbol, f"Rotasi penuh — {symbol} tidak di top 5 baru"))

    return to_close

def get_portfolio_summary(positions, current_prices):
    """Summary portfolio untuk Telegram."""
    if not positions:
        return "Tidak ada posisi narrative aktif"

    lines = ["📊 NARRATIVE PORTFOLIO:"]
    total_pnl = 0
    for sym, pos in positions.items():
        price = current_prices.get(sym, pos.get("entry_price", 0))
        entry = pos.get("entry_price", 0)
        qty = pos.get("qty", 0)
        if entry > 0:
            pnl = (price - entry) * qty
            pnl_pct = (price - entry) / entry * 100
            total_pnl += pnl
            emoji = "🟢" if pnl >= 0 else "🔴"
            lines.append(f"{emoji} {sym} [{pos.get('narrative','?')}] "
                        f"PnL:  ({pnl_pct:+.1f}%)")
    lines.append(f"Total PnL: ")
    return "\n".join(lines)

if __name__ == "__main__":
    # Test
    print("=== PORTFOLIO MANAGER TEST ===")
    narrative_state = {
        "active_narratives": [("CRYPTO_BULL", 13), ("AI_TECH", 9)],
        "selected_assets": [
            {"symbol":"BTC/USDT","narrative":"CRYPTO_BULL","category":"crypto","tp_pct":50,"sl_pct":20},
            {"symbol":"ETH/USDT","narrative":"CRYPTO_BULL","category":"crypto","tp_pct":50,"sl_pct":20},
            {"symbol":"NVDA","narrative":"AI_TECH","category":"stocks","tp_pct":40,"sl_pct":15},
        ],
        "allocation": {"crypto":35,"stocks":35,"commodities":15,"cash":15},
        "rotation_urgency": "medium",
    }
    alloc = alloc_per_asset(narrative_state, balance=1000)
    print("\nAlokasi per aset:")
    for sym, info in alloc.items():
        print(f"  {sym}:  [{info['narrative']}] TP:{info['tp_pct']}% SL:{info['sl_pct']}%")

    # Test partial TP
    print("\nTest Partial TP:")
    action, qty, reason = check_partial_tp("BTC/USDT", 70000, 91000, 0.01, 50)
    print(f"  BTC +30%: {action} qty={qty:.4f} | {reason}")
    action, qty, reason = check_partial_tp("BTC/USDT", 70000, 105000, 0.01, 50)
    print(f"  BTC +50%: {action} qty={qty:.4f} | {reason}")
    action, qty, reason = check_partial_tp("BTC/USDT", 70000, 126000, 0.01, 50)
    print(f"  BTC +80% (full TP): {action} qty={qty:.4f} | {reason}")

    # Test rotation
    print("\nTest Rotation:")
    positions = {
        "BTC/USDT": {"narrative":"CRYPTO_BULL","entry_price":70000,"qty":0.01},
        "AAPL": {"narrative":"SEMIS_SUPPLY","entry_price":180,"qty":5},
    }
    to_close = check_rotation_needed(narrative_state, positions)
    print(f"  Perlu di-close: {to_close}")
