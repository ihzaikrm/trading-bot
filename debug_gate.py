import ccxt
ex = ccxt.gate()
t = ex.fetch_ticker('BTC/USDT')
print(f"last: {t['last']}")
print(f"percentage: {t['percentage']}")
print(f"Keys: {list(t.keys())[:10]}")
