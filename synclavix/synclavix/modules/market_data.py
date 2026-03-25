import requests

def get_btc_price():
    """Get BTC price from multiple free APIs."""
    # Try CryptoCompare
    try:
        url = "https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if "USD" in data:
            return data["USD"]
    except Exception as e:
        print(f"CryptoCompare error: {e}")

    # Try CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if "bitcoin" in data and "usd" in data["bitcoin"]:
            return data["bitcoin"]["usd"]
    except Exception as e:
        print(f"CoinGecko error: {e}")

    # Fallback
    return 68700.0
