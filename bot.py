import asyncio, json, os, sys
from datetime import datetime
from collections import Counter

sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv()

# Import dari modul baru
from config.assets import ASSETS
from config.trading_params import STOP_LOSS_PCT, TAKE_PROFIT_PCT, LEVERAGE
from core.market_data import get_asset_data, is_market_open
from core.signal_engine import get_signal, mtf_bias
from core.risk_manager import force_close_position
from core.notifier import tg
from core.llm_clients import call_all_llms

PAPER_FILE = "logs/paper_trades.json"

def load_trades():
    if os.path.exists(PAPER_FILE):
        with open(PAPER_FILE) as f:
            return json.load(f)
    return {"balance": 1000.0, "trades": [], "positions": {}, "shorts": {}}

def save_trades(data):
    os.makedirs("logs", exist_ok=True)
    with open(PAPER_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=== MULTI-ASSET BOT (MTF + LONG/SHORT) | "+now+" ===")
    data = load_trades()
    positions = data.get("positions", {})
    shorts = data.get("shorts", {})

    # Circuit breaker
    initial = 1000.0
    current = data["balance"]
    drawdown = max(0, (initial - current) / initial * 100)
    if drawdown > 3:
        msg = "⛔ CIRCUIT BREAKER: Drawdown "+str(round(drawdown,1))+"% > 3%!"
        print(msg); tg(msg)
        return

    # Alokasi per aset (dengan leverage)
    alloc = data["balance"] / len(ASSETS) * LEVERAGE

    print("\nAnalisa 3 aset (MTF)...")
    summary = []
    for name, info in ASSETS.items():
        # Cek apakah pasar buka (untuk saham)
        if not is_market_open(info["type"]):
            print(f"  [{name}] Pasar tutup (weekend), lewati")
            summary.append(f"{name}: SKIP (market closed)")
            continue

        print(f"\n  [{name}] Mengambil data MTF...")
        asset_data = get_asset_data(name, info)
        if not asset_data or "price" not in asset_data:
            print(f"  {name}: gagal ambil data")
            continue

        price = asset_data["price"]
        change = asset_data["change"]
        bias = mtf_bias(asset_data)

        # Cek SL/TP
        long_pos = positions.get(name)
        short_pos = shorts.get(name)

        if long_pos:
            entry = long_pos["entry_price"]
            pnl_pct = (price - entry) / entry * 100 * LEVERAGE
            if pnl_pct <= -STOP_LOSS_PCT:
                data = force_close_position(data, name, price, "STOP_LOSS")
                positions = data.get("positions", {})
                shorts = data.get("shorts", {})
                continue
            elif pnl_pct >= TAKE_PROFIT_PCT:
                data = force_close_position(data, name, price, "TAKE_PROFIT")
                positions = data.get("positions", {})
                shorts = data.get("shorts", {})
                continue

        if short_pos:
            entry = short_pos["entry_price"]
            pnl_pct = (entry - price) / entry * 100 * LEVERAGE
            if pnl_pct <= -STOP_LOSS_PCT:
                data = force_close_position(data, name, price, "STOP_LOSS")
                positions = data.get("positions", {})
                shorts = data.get("shorts", {})
                continue
            elif pnl_pct >= TAKE_PROFIT_PCT:
                data = force_close_position(data, name, price, "TAKE_PROFIT")
                positions = data.get("positions", {})
                shorts = data.get("shorts", {})
                continue

        # Cetak ringkasan
        for tf in ["1d", "4h", "1h"]:
            if tf in asset_data:
                ind = asset_data[tf]
                print(f"    {tf}: RSI:{ind['rsi']} | MACD:{ind['macd_cross']} | EMA:{ind['ema_trend']} | BB:{ind['bb_pos']}")
        print(f"    Bias MTF: {bias}")

        signal, conf, votes, details, bias = await get_signal(info["name"], asset_data)
        print(f"  -> {signal} conf:{conf} votes:{votes}")
        summary.append(f"{name}: {signal} ({conf}) [{bias}]")

        long_pos = positions.get(name)
        short_pos = shorts.get(name)

        # Open Long
        if signal == "BUY" and conf >= 0.55 and votes >= 3 and not long_pos and not short_pos and alloc > 10:
            qty = alloc / price
            positions[name] = {"entry_price": price, "qty": qty, "amount": alloc/LEVERAGE, "time": now}
            data["balance"] -= alloc/LEVERAGE
            msg = (f"🟢 BUY {info['name']} (Leverage {LEVERAGE}x)\n"
                   f"Harga: ${price} | 24h: {change}%\n"
                   f"Qty: {round(qty,6)} | Notional: ${round(alloc,2)}\n"
                   f"MTF Bias: {bias}\n"
                   f"Conf: {conf} ({votes} votes)\n\n"
                   + "\n".join(details))
            print(f"  [BUY] {name}")
            tg(msg)

        # Close Long
        elif signal == "SELL" and long_pos:
            pnl = (price - long_pos["entry_price"]) * long_pos["qty"]
            data["balance"] += long_pos["amount"] + pnl
            data["trades"].append({**long_pos, "asset": name, "type": "long",
                                   "exit_price": price, "pnl": round(pnl,2), "exit_time": now})
            del positions[name]
            emoji = "✅" if pnl > 0 else "🔴"
            msg = (f"{emoji} SELL (Close Long) {info['name']}\n"
                   f"Entry: ${long_pos['entry_price']} | Exit: ${price}\n"
                   f"PnL: ${round(pnl,2)} | Balance: ${round(data['balance'],2)}")
            print(f"  [SELL] {name} PnL: ${round(pnl,2)}")
            tg(msg)

        # Open Short
        elif signal == "SHORT" and conf >= 0.55 and votes >= 3 and not short_pos and not long_pos and alloc > 10:
            qty = alloc / price
            shorts[name] = {"entry_price": price, "qty": qty, "amount": alloc/LEVERAGE, "time": now}
            data["balance"] -= alloc/LEVERAGE
            msg = (f"🔴 SHORT {info['name']} (Leverage {LEVERAGE}x)\n"
                   f"Harga: ${price} | 24h: {change}%\n"
                   f"Qty: {round(qty,6)} | Notional: ${round(alloc,2)}\n"
                   f"MTF Bias: {bias}\n"
                   f"Conf: {conf} ({votes} votes)\n\n"
                   + "\n".join(details))
            print(f"  [SHORT] {name}")
            tg(msg)

        # Close Short
        elif signal == "COVER" and short_pos:
            pnl = (short_pos["entry_price"] - price) * short_pos["qty"]
            data["balance"] += short_pos["amount"] + pnl
            data["trades"].append({**short_pos, "asset": name, "type": "short",
                                   "exit_price": price, "pnl": round(pnl,2), "exit_time": now})
            del shorts[name]
            emoji = "✅" if pnl > 0 else "🔴"
            msg = (f"{emoji} COVER (Close Short) {info['name']}\n"
                   f"Entry: ${short_pos['entry_price']} | Exit: ${price}\n"
                   f"PnL: ${round(pnl,2)} | Balance: ${round(data['balance'],2)}")
            print(f"  [COVER] {name} PnL: ${round(pnl,2)}")
            tg(msg)

    data["positions"] = positions
    data["shorts"] = shorts
    save_trades(data)

    # Status akhir
    trades = data["trades"]
    wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    winrate = str(round(wins/len(trades)*100))+"%" if trades else "N/A"
    total_pnl = sum(t.get("pnl",0) for t in trades)
    open_long = ", ".join(positions.keys()) if positions else "Tidak ada"
    open_short = ", ".join(shorts.keys()) if shorts else "Tidak ada"

    status = (f"📊 MULTI-ASSET STATUS {now}\n"
              f"Balance: ${round(data['balance'],2)} (Leverage {LEVERAGE}x)\n"
              f"Drawdown: {round(drawdown,1)}%\n"
              f"Long: {open_long}\n"
              f"Short: {open_short}\n\n"
              + "\n".join(summary) + "\n\n"
              f"Trade: {len(trades)} | Winrate: {winrate}\n"
              f"Total PnL: ${round(total_pnl,2)}")
    print("\n"+status)
    tg(status)
    print("\n=== SELESAI ===")

if __name__ == "__main__":
    asyncio.run(main())