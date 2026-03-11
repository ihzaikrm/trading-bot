import asyncio, json, os, sys, re, requests
from datetime import datetime
from collections import Counter
import ccxt

sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv()
from core.llm_clients import call_all_llms

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PAPER_FILE = "logs/paper_trades.json"

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"  [TG] Gagal: {e}")

def load_trades():
    if os.path.exists(PAPER_FILE):
        with open(PAPER_FILE) as f:
            return json.load(f)
    return {"balance": 1000.0, "trades": [], "open_position": None}

def save_trades(data):
    with open(PAPER_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_price():
    ex = ccxt.gate()
    t = ex.fetch_ticker("BTC/USDT")
    price = float(t.get("last") or t.get("close") or t.get("bid") or 0)
    change = float(t.get("percentage") or t.get("change") or 0)
    ohlcv = ex.fetch_ohlcv("BTC/USDT", "1d", limit=14)
    closes = [c[4] for c in ohlcv]
    gains = [max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
    losses = [max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
    avg_g = sum(gains)/len(gains) if gains else 1
    avg_l = sum(losses)/len(losses) if losses else 1
    rsi = 100 - (100/(1+avg_g/avg_l)) if avg_l > 0 else 50
    return round(price, 2), round(change, 2), round(rsi, 2)

async def get_signal(price, change, rsi):
    prompt = "Data BTC/USDT:\nHarga: " + str(price) + "\n24h: " + str(change) + "%\nRSI: " + str(rsi) + '\n\nBalas HANYA JSON:\n{"signal":"BUY/SELL/HOLD","confidence":0.5,"reason":"alasan singkat"}'
    results = await call_all_llms("Analis trading crypto. Balas JSON saja.", prompt)
    signals, confs, details = [], [], []
    for name, (ok, resp) in results.items():
        if ok:
            try:
                r = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group())
                signals.append(r["signal"])
                confs.append(r.get("confidence", 0.5))
                details.append(f"  {name}: {r['signal']} ({r.get('confidence',0.5):.0%})")
            except: pass
    if not signals:
        return "HOLD", 0.5, 0, []
    most = Counter(signals).most_common(1)[0]
    return most[0], round(sum(confs)/len(confs), 2), most[1], details

async def run_cycle(cycle_num, data):
    print(f"\n--- SIKLUS {cycle_num} | {datetime.now().strftime('%H:%M:%S')} ---")
    price, change, rsi = get_price()
    initial = 1000.0
    current = data["balance"]
    pos = data.get("open_position")
    if pos:
        current += pos["amount"] + (price - pos["entry_price"]) * pos["qty"]
    drawdown = max(0, (initial - current) / initial * 100)

    if drawdown > 5:
        msg = "CIRCUIT BREAKER: Drawdown " + str(round(drawdown,1)) + "% > 5%"
        print(msg); tg(msg)
        return False

    print(f"  BTC: {price} | 24h: {change}% | RSI: {rsi}")
    signal, conf, votes, details = await get_signal(price, change, rsi)
    print(f"  Sinyal: {signal} | Conf: {conf} | Votes: {votes}")

    if signal == "BUY" and conf >= 0.6 and not pos:
        amount = data["balance"] * 0.20
        qty = amount / price
        data["open_position"] = {"entry_price": price, "qty": qty, "amount": amount, "time": datetime.now().isoformat()}
        data["balance"] -= amount
        msg = "BUY BTC\nHarga: " + str(price) + "\nQty: " + str(round(qty,6)) + "\nAmount: " + str(round(amount,2)) + "\nConf: " + str(conf) + "\nRSI: " + str(rsi) + "\n\n" + "\n".join(details)
        print(f"  -> BELI {round(qty,6)} BTC"); tg(msg)

    elif signal == "SELL" and pos:
        pnl = (price - pos["entry_price"]) * pos["qty"]
        data["balance"] += pos["amount"] + pnl
        data["trades"].append({**pos, "exit_price": price, "pnl": round(pnl,2), "exit_time": datetime.now().isoformat()})
        data["open_position"] = None
        msg = "SELL BTC\nEntry: " + str(pos["entry_price"]) + "\nExit: " + str(price) + "\nPnL: " + str(round(pnl,2)) + "\nBalance: " + str(round(data["balance"],2))
        print(f"  -> JUAL PnL: {round(pnl,2)}"); tg(msg)
    else:
        print(f"  -> {signal} tidak ada aksi")

    trades = data["trades"]
    wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    winrate = str(round(wins/len(trades)*100)) + "%" if trades else "N/A"
    total_pnl = sum(t.get("pnl",0) for t in trades)
    status = "STATUS (Siklus " + str(cycle_num) + ")\nBalance: " + str(round(data["balance"],2)) + "\nBTC: " + str(price) + " (" + str(change) + "%)\nSinyal: " + signal + " conf:" + str(conf) + " votes:" + str(votes) + "\nRSI: " + str(rsi) + "\nDrawdown: " + str(round(drawdown,1)) + "%\nTrade: " + str(len(trades)) + " | Winrate: " + winrate + "\nPnL: " + str(round(total_pnl,2))
    print("  " + status.replace("\n", " | ")); tg(status)
    save_trades(data)
    return True

async def main():
    print("\n=== PHASE 5 - TRADING BOT ===")
    data = load_trades()
    tg("Trading Bot v2 AKTIF\nModal: 1000\nCircuit Breaker: 5%\nMonitoring BTC/USDT...")
    for i in range(1, 4):
        ok = await run_cycle(i, data)
        if not ok: break
        if i < 3:
            print("\n  Menunggu 10 detik...")
            await asyncio.sleep(10)
    print("\n=== SELESAI ===")
    tg("Sesi selesai! Bot standby.")

asyncio.run(main())
