import ccxt, yfinance as yf, asyncio, aiohttp, requests

def test_crypto():
    try:
        exchange = ccxt.kucoin()
        for pair in ['BTC/USDT', 'ETH/USDT']:
            t = exchange.fetch_ticker(pair)
            print(f"OK {pair}:  | 24h: {t['percentage']:+.2f}%")
    except Exception as e:
        print(f"GAGAL crypto: {e}")

def test_stocks():
    for sym in ['AAPL', 'NVDA', 'GC=F']:
        try:
            h = yf.Ticker(sym).history(period='1d')
            if not h.empty:
                print(f"OK {sym}: ")
        except Exception as e:
            print(f"GAGAL {sym}: {e}")

def test_forex():
    # Gunakan frankfurter.app - gratis tanpa API key
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR,IDR,GBP", timeout=10)
        data = r.json()
        for k, v in data['rates'].items():
            print(f"OK USD/{k}: {v:,.4f}")
    except Exception as e:
        print(f"GAGAL forex: {e}")

print("\n=== PHASE 2 - MARKET DATA TEST ===\n")
print("[1/3] CRYPTO (KuCoin)")
test_crypto()
print("\n[2/3] STOCKS & COMMODITIES (yfinance)")
test_stocks()
print("\n[3/3] FOREX (frankfurter.app)")
test_forex()
print("\n=== SELESAI ===")
