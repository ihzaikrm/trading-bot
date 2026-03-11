import ccxt

# Test beberapa exchange yang tidak diblokir di Indonesia
exchanges_to_test = ['gate', 'mexc', 'bybit', 'okx', 'htx']

for ex_id in exchanges_to_test:
    try:
        ex = getattr(ccxt, ex_id)()
        ticker = ex.fetch_ticker('BTC/USDT')
        print(f"OK {ex_id}: BTC = ")
        break
    except Exception as e:
        print(f"GAGAL {ex_id}: {str(e)[:60]}")
