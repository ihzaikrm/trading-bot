import ccxt, yfinance as yf, requests, asyncio, sys, os
sys.path.insert(0, os.getcwd())
from core.llm_clients import call_all_llms

def get_market_data(symbol='BTC/USDT'):
    ex = ccxt.kucoin()
    t = ex.fetch_ticker(symbol)
    ohlcv = ex.fetch_ohlcv(symbol, '1d', limit=14)
    closes = [c[4] for c in ohlcv]
    # Hitung RSI sederhana
    gains = [max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
    losses = [max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
    avg_g = sum(gains)/len(gains)
    avg_l = sum(losses)/len(losses)
    rsi = 100 - (100/(1+avg_g/avg_l)) if avg_l > 0 else 50
    return {
        'symbol': symbol,
        'price': t['last'],
        'change_24h': t['percentage'],
        'high_24h': t['high'],
        'low_24h': t['low'],
        'volume_24h': t['quoteVolume'],
        'rsi_14': round(rsi, 2)
    }

async def analyze_with_llms(data):
    prompt = f"""Analisis data trading berikut dan berikan sinyal:

Aset: {data['symbol']}
Harga: 
Perubahan 24h: {data['change_24h']:+.2f}%
High 24h: 
Low 24h: 
Volume 24h: 
RSI(14): {data['rsi_14']}

Balas HANYA dengan JSON:
{{"signal":"BUY/SELL/HOLD","confidence":0.0-1.0,"reason":"alasan singkat max 10 kata"}}"""

    sys_prompt = "Kamu adalah analis trading crypto profesional. Balas hanya JSON, tanpa penjelasan tambahan."
    results = await call_all_llms(sys_prompt, prompt)
    return results

async def main():
    print("\n" + "="*55)
    print("   PHASE 3 - LLM + MARKET DATA INTEGRATION")
    print("="*55)

    print("\n📊 Mengambil data market BTC/USDT...")
    data = get_market_data('BTC/USDT')
    print(f"   Harga : ")
    print(f"   24h   : {data['change_24h']:+.2f}%")
    print(f"   RSI   : {data['rsi_14']}")

    print("\n🤖 Mengirim ke 6 LLM untuk analisis...\n")
    results = await analyze_with_llms(data)

    print(f"{'LLM':<12} {'Status':<8} {'Signal':<8} {'Conf':<6} {'Alasan'}")
    print("-"*65)

    signals = []
    for name, (ok, resp) in results.items():
        if ok:
            import json, re
            try:
                clean = re.search(r'\{.*\}', resp, re.DOTALL).group()
                r = json.loads(clean)
                sig = r.get('signal','?')
                conf = r.get('confidence', 0)
                reason = r.get('reason','')[:35]
                signals.append(sig)
                print(f"{name:<12} {'OK':<8} {sig:<8} {conf:<6} {reason}")
            except:
                print(f"{name:<12} {'PARSE ERR':<8} -       -      {resp[:30]}")
        else:
            print(f"{name:<12} {'GAGAL':<8} -       -      {resp[:35]}")

    if signals:
        from collections import Counter
        most = Counter(signals).most_common(1)[0]
        print(f"\n{'='*55}")
        print(f"  KONSENSUS: {most[0]} ({most[1]}/{len(signals)} LLM setuju)")
        print(f"{'='*55}")

asyncio.run(main())
