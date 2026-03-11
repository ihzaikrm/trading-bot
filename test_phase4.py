import asyncio, json, os, sys, re
from datetime import datetime
from collections import Counter
import ccxt, requests

sys.path.insert(0, os.getcwd())
from core.llm_clients import call_all_llms

PAPER_FILE = "logs/paper_trades.json"
os.makedirs("logs", exist_ok=True)

def load_trades():
    if os.path.exists(PAPER_FILE):
        with open(PAPER_FILE) as f:
            return json.load(f)
    return {"balance": 1000.0, "trades": [], "open_position": None}

def save_trades(data):
    with open(PAPER_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_price(symbol='BTC/USDT'):
    ex = ccxt.gate()
    t = ex.fetch_ticker(symbol)
    ohlcv = ex.fetch_ohlcv(symbol, '1d', limit=14)
    closes = [c[4] for c in ohlcv]
    gains = [max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
    losses = [max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
    avg_g = sum(gains)/len(gains) if gains else 1
    avg_l = sum(losses)/len(losses) if losses else 1
    rsi = 100 - (100/(1+avg_g/avg_l)) if avg_l > 0 else 50
    return round(t['last'], 2), round(t['percentage'], 2), round(rsi, 2)

async def get_signal(price, change, rsi):
    prompt = f"""Data BTC/USDT:
Harga: 
Perubahan 24h: {change:+.2f}%
RSI(14): {rsi}

Balas HANYA JSON:
{{"signal":"BUY/SELL/HOLD","confidence":0.0-1.0,"reason":"max 8 kata"}}"""
    sys_p = "Analis trading crypto. Balas JSON saja."
    results = await call_all_llms(sys_p, prompt)
    signals, confs = [], []
    for name, (ok, resp) in results.items():
        if ok:
            try:
                r = json.loads(re.search(r'\{.*\}', resp, re.DOTALL).group())
                signals.append(r['signal'])
                confs.append(r.get('confidence', 0.5))
            except: pass
    if not signals:
        return "HOLD", 0.5, 0
    most = Counter(signals).most_common(1)[0]
    avg_conf = sum(confs)/len(confs)
    return most[0], round(avg_conf, 2), most[1]

def print_status(data, price):
    print(f"\n{'='*55}")
    print(f"  PAPER TRADING STATUS")
    print(f"{'='*55}")
    print(f"  Balance  : ")
    pos = data.get('open_position')
    if pos:
        pnl = (price - pos['entry_price']) * pos['qty']
        pnl_pct = (price/pos['entry_price']-1)*100
        print(f"  Posisi   : LONG {pos['qty']:.6f} BTC @ ")
        print(f"  PnL      :  ({pnl_pct:+.2f}%)")
    else:
        print(f"  Posisi   : Tidak ada")
    trades = data['trades']
    if trades:
        wins = sum(1 for t in trades if t.get('pnl',0) > 0)
        print(f"  Total Trade: {len(trades)} | Winrate: {wins/len(trades)*100:.0f}%")
        total_pnl = sum(t.get('pnl',0) for t in trades)
        print(f"  Total PnL  : ")

async def main():
    print("\n" + "="*55)
    print("   PHASE 4 - PAPER TRADING BOT")
    print("   Modal:  | Simulasi 3 siklus")
    print("="*55)

    data = load_trades()
    symbol = 'BTC/USDT'
    size_pct = 0.20

    for cycle in range(1, 4):
        print(f"\n{'-'*55}")
        print(f"  SIKLUS {cycle}/3 - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'-'*55}")

        price, change, rsi = get_price(symbol)
        print(f"  BTC:  | 24h: {change:+.2f}% | RSI: {rsi}")

        print(f"  Menganalisis dengan LLM...")
        signal, conf, votes = await get_signal(price, change, rsi)
        print(f"  Sinyal: {signal} | Conf: {conf} | Votes: {votes}")

        pos = data.get('open_position')

        if signal == 'BUY' and conf >= 0.6 and not pos:
            amount = data['balance'] * size_pct
            qty = amount / price
            data['open_position'] = {
                'entry_price': price, 'qty': qty,
                'amount': amount, 'time': datetime.now().isoformat()
            }
            data['balance'] -= amount
            print(f"  -> BELI {qty:.6f} BTC @  ()")

        elif signal == 'SELL' and pos:
            pnl = (price - pos['entry_price']) * pos['qty']
            data['balance'] += pos['amount'] + pnl
            trade = {**pos, 'exit_price': price, 'pnl': round(pnl,2),
                     'exit_time': datetime.now().isoformat()}
            data['trades'].append(trade)
            data['open_position'] = None
            print(f"  -> JUAL @  | PnL: ")

        else:
            print(f"  -> {signal} - tidak ada aksi")

        print_status(data, price)
        save_trades(data)

        if cycle < 3:
            print(f"\n  Menunggu 5 detik...")
            await asyncio.sleep(5)

    print(f"\n{'='*55}")
    print(f"  PHASE 4 SELESAI!")
    print(f"{'='*55}")

asyncio.run(main())
