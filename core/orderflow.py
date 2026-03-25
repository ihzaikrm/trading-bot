import ccxt
import time

def get_orderbook_imbalance(symbol="BTC/USDT", depth=10):
    """
    Ambil order book dari exchange, hitung imbalance ratio.
    Nilai positif = buying pressure, negatif = selling pressure.
    """
    try:
        exchange = ccxt.gate()
        orderbook = exchange.fetch_order_book(symbol, depth)
        bids = orderbook['bids']
        asks = orderbook['asks']
        bid_vol = sum(price*amount for price, amount in bids[:depth])
        ask_vol = sum(price*amount for price, amount in asks[:depth])
        total = bid_vol + ask_vol
        if total == 0:
            return 0
        return (bid_vol - ask_vol) / total
    except Exception as e:
        print(f"Order book error: {e}")
        return None

def get_liquidity_levels(symbol="BTC/USDT", threshold=1000):
    """
    Cari level harga dengan akumulasi order besar.
    """
    try:
        exchange = ccxt.gate()
        orderbook = exchange.fetch_order_book(symbol, 100)
        bids = orderbook['bids']
        asks = orderbook['asks']
        levels = []
        # Cari level bid yang signifikan
        for price, amount in bids:
            if amount * price > threshold:
                levels.append(('bid', price, amount))
        for price, amount in asks:
            if amount * price > threshold:
                levels.append(('ask', price, amount))
        return sorted(levels, key=lambda x: x[2], reverse=True)[:5]
    except Exception as e:
        print(f"Liquidity levels error: {e}")
        return []