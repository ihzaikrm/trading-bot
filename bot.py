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
from core.llm_performance import evaluate_predictions
from core.command_handler import handle_commands   # <-- TAMBAHAN

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

def calculate_equity(data, current_prices):
    """Hitung equity total = balance + unrealized PnL semua posisi"""
    equity = data["balance"]
    positions = data.get("positions", {})
    shorts = data.get("shorts", {})
    
    for symbol, pos in positions.items():
        if symbol in current_prices:
            price = current_prices[symbol]
            pnl = (price - pos["entry_price"]) * pos["qty"]
            equity += pnl
    for symbol, pos in shorts.items():
        if symbol in current_prices:
            price = current_prices[symbol]
            pnl = (pos["entry_price"] - price) * pos["qty"]
            equity += pnl
    return equity

def generate_dashboard(data, perf, equity, drawdown):
    """Buat file HTML dashboard dengan data terkini"""
    import os
    from datetime import datetime
    dashboard_dir = "dashboard"
    os.makedirs(dashboard_dir, exist_ok=True)
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Trading Bot Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; }}
        .status {{ background: #e3f2fd; padding: 15px; border-radius: 5px; }}
        .position {{ border-left: 4px solid #ff9800; padding: 10px; margin: 10px 0; }}
        .table {{ width: 100%; border-collapse: collapse; }}
        .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .table th {{ background-color: #f2f2f2; }}
        .good {{ color: green; }}
        .bad {{ color: red; }}
    </style>
</head>
<body>
<div class="container">
    <h1>Trading Bot Dashboard</h1>
    <p>Last updated: {now} UTC</p>
    
    <div class="status">
        <h2>Account Summary</h2>
        <p>Balance: ${data.get('balance',0):.2f}</p>
        <p>Equity: ${equity:.2f}</p>
        <p>Drawdown: {drawdown:.1f}%</p>
    </div>
    
    <h2>Open Positions</h2>
    <div id="positions">
"""
    # Tambah posisi long
    for sym, pos in data.get('positions',{}).items():
        html += f"""
        <div class="position">
            <strong>{sym}</strong> (Long) - Entry: ${pos['entry_price']:.2f}, Qty: {pos['qty']:.4f}
        </div>"""
    for sym, pos in data.get('shorts',{}).items():
        html += f"""
        <div class="position">
            <strong>{sym}</strong> (Short) - Entry: ${pos['entry_price']:.2f}, Qty: {pos['qty']:.4f}
        </div>"""
    if not data.get('positions') and not data.get('shorts'):
        html += "<p>No open positions.</p>"
    
    html += """
    </div>
    
    <h2>Recent Trades</h2>
    <table class="table">
        <tr><th>Asset</th><th>Type</th><th>Entry</th><th>Exit</th><th>PnL</th></tr>
"""
    for trade in data.get('trades',[])[-10:]:
        pnl = trade.get('pnl',0)
        cls = "good" if pnl > 0 else "bad"
        html += f"""
        <tr>
            <td>{trade.get('asset','')}</td>
            <td>{trade.get('type','')}</td>
            <td>${trade.get('entry_price',0):.2f}</td>
            <td>${trade.get('exit_price',0):.2f}</td>
            <td class="{cls}">${pnl:.2f}</td>
        </tr>"""
    html += """
    </table>
    
    <h2>LLM Performance</h2>
    <table class="table">
        <tr><th>LLM</th><th>Correct</th><th>Total</th><th>Accuracy</th></tr>
"""
    for llm, stats in perf.items():
        acc = stats.get('accuracy',0)*100
        html += f"""
        <tr>
            <td>{llm}</td>
            <td>{stats.get('correct',0)}</td>
            <td>{stats.get('total',0)}</td>
            <td>{acc:.1f}%</td>
        </tr>"""
    html += """
    </table>
</div>
</body>
</html>"""
    with open(os.path.join(dashboard_dir, "index.html"), "w") as f:
        f.write(html)
    print("[Dashboard] Generated dashboard/index.html")

async def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=== MULTI-ASSET BOT (MTF + LONG/SHORT) | "+now+" ===")
    data = load_trades()
    
    # ===== TAMBAHAN: Proses perintah Telegram =====
    handle_commands(data, os.getenv("TELEGRAM_CHAT_ID"))
    
    positions = data.get("positions", {})
    shorts = data.get("shorts", {})

    # Kumpulkan harga terkini untuk semua aset (untuk hitung equity dan evaluasi prediksi)
    current_prices = {}
    for name, info in ASSETS.items():
        if not is_market_open(info["type"]):
            continue
        asset_data = get_asset_data(name, info)
        if asset_data and "price" in asset_data:
            current_prices[name] = asset_data["price"]

    # Evaluasi prediksi sebelumnya dan dapatkan performa terbaru
    perf = evaluate_predictions(current_prices)

    # Hitung equity dan drawdown
    initial = 1000.0
    equity = calculate_equity(data, current_prices)
    drawdown = max(0, (initial - equity) / initial * 100)

    # ===== TAMBAHAN: Cek apakah bot di-pause =====
    if os.path.exists("logs/pause.txt"):
        print("⏸️ Bot dalam mode pause. Tidak melakukan trading baru.")
        tg("⏸️ Bot dalam mode pause. Hanya akan memonitor posisi.")
        can_open_new = False
    else:
        can_open_new = drawdown <= 3.0

    if drawdown > 3 and not os.path.exists("logs/pause.txt"):
        msg = f"⚠️ CIRCUIT BREAKER: Drawdown {round(drawdown,1)}% > 3%! Hanya akan menutup posisi, tidak membuka baru."
        print(msg); tg(msg)

    # Alokasi per aset (hanya digunakan jika can_open_new)
    alloc = data["balance"] / len(ASSETS) * LEVERAGE

    print("\nAnalisa 3 aset (MTF)...")
    summary = []
    for name, info in ASSETS.items():
        # Cek pasar buka
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

        # Cek SL/TP untuk posisi existing
        long_pos = positions.get(name)
        short_pos = shorts.get(name)

        if long_pos:
            entry = long_pos["entry_price"]
            pnl_pct = (price - entry) / entry * 100 * LEVERAGE
            if pnl_pct <= -STOP_LOSS_PCT:
                data = force_close_position(data, name, price, "STOP_LOSS")
                positions = data.get("positions", {})
                shorts = data.get("shorts", {})
                # Update equity setelah close
                equity = calculate_equity(data, current_prices)
                drawdown = max(0, (initial - equity) / initial * 100)
                continue
            elif pnl_pct >= TAKE_PROFIT_PCT:
                data = force_close_position(data, name, price, "TAKE_PROFIT")
                positions = data.get("positions", {})
                shorts = data.get("shorts", {})
                equity = calculate_equity(data, current_prices)
                drawdown = max(0, (initial - equity) / initial * 100)
                continue

        if short_pos:
            entry = short_pos["entry_price"]
            pnl_pct = (entry - price) / entry * 100 * LEVERAGE
            if pnl_pct <= -STOP_LOSS_PCT:
                data = force_close_position(data, name, price, "STOP_LOSS")
                positions = data.get("positions", {})
                shorts = data.get("shorts", {})
                equity = calculate_equity(data, current_prices)
                drawdown = max(0, (initial - equity) / initial * 100)
                continue
            elif pnl_pct >= TAKE_PROFIT_PCT:
                data = force_close_position(data, name, price, "TAKE_PROFIT")
                positions = data.get("positions", {})
                shorts = data.get("shorts", {})
                equity = calculate_equity(data, current_prices)
                drawdown = max(0, (initial - equity) / initial * 100)
                continue

        # Cetak ringkasan teknikal
        for tf in ["1d", "4h", "1h"]:
            if tf in asset_data:
                ind = asset_data[tf]
                print(f"    {tf}: RSI:{ind['rsi']} | MACD:{ind['macd_cross']} | EMA:{ind['ema_trend']} | BB:{ind['bb_pos']}")
        print(f"    Bias MTF: {bias}")

        # Dapatkan sinyal dengan bobot dinamis
        signal, conf, votes, details, bias = await get_signal(info["name"], asset_data, now, perf)
        print(f"  -> {signal} conf:{conf} votes:{votes}")
        summary.append(f"{name}: {signal} ({conf}) [{bias}]")

        long_pos = positions.get(name)
        short_pos = shorts.get(name)

        # Open Long hanya jika can_open_new
        if can_open_new and signal == "BUY" and conf >= 0.55 and votes >= 3 and not long_pos and not short_pos and alloc > 10:
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

        # Close Long (tetap bisa dilakukan meskipun drawdown tinggi)
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

        # Open Short hanya jika can_open_new
        elif can_open_new and signal == "SHORT" and conf >= 0.55 and votes >= 3 and not short_pos and not long_pos and alloc > 10:
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

        # Close Short (tetap bisa)
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

    # Generate dashboard HTML
    generate_dashboard(data, perf, equity, drawdown)

    # Hitung ulang equity untuk status akhir (sudah dihitung)
    # Status ringkasan
    trades = data["trades"]
    wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    winrate = str(round(wins/len(trades)*100))+"%" if trades else "N/A"
    total_pnl = sum(t.get("pnl",0) for t in trades)
    open_long = ", ".join(positions.keys()) if positions else "Tidak ada"
    open_short = ", ".join(shorts.keys()) if shorts else "Tidak ada"

    status = (f"📊 MULTI-ASSET STATUS {now}\n"
              f"Equity: ${round(equity,2)} (Balance: ${round(data['balance'],2)})\n"
              f"Drawdown: {round(drawdown,1)}%\n"
              f"Long: {open_long}\n"
              f"Short: {open_short}\n\n"
              + "\n".join(summary) + "\n\n"
              f"Trade: {len(trades)} | Winrate: {winrate}\n"
              f"Total PnL: ${round(total_pnl,2)}")
    
    # Tambahkan link dashboard
    dashboard_url = "https://htmlpreview.github.io/?https://github.com/ihzaikrm/trading-bot/blob/main/dashboard/index.html"
    status += f"\n\n📈 Monitor: {dashboard_url}"
    
    print("\n"+status)
    tg(status)
    print("\n=== SELESAI ===")

if __name__ == "__main__":
    asyncio.run(main())