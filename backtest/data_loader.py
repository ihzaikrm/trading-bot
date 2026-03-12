# backtest/data_loader.py
import ccxt
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def load_crypto_data(symbol, start_date, end_date, timeframe='1d'):
    """
    Ambil data historis crypto dari Gate.io via ccxt
    """
    exchange = ccxt.gate()  # pakai gate, lebih stabil
    since = exchange.parse8601(start_date + 'T00:00:00Z')
    end = exchange.parse8601(end_date + 'T00:00:00Z')
    all_ohlcv = []
    while since < end:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        except Exception as e:
            print(f"Error fetch: {e}")
            break
        if len(ohlcv) == 0:
            break
        all_ohlcv += ohlcv
        since = ohlcv[-1][0] + 1
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def load_stock_data(symbol, start_date, end_date, interval='1d'):
    """
    Ambil data historis saham dari yfinance
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date, interval=interval)
    if df.empty:
        return None
    df.rename(columns={'Close': 'close'}, inplace=True)
    return df[['close']]

def load_data(asset_type, symbol, start_date, end_date, timeframe='1d'):
    if asset_type == 'crypto':
        return load_crypto_data(symbol, start_date, end_date, timeframe)
    else:
        return load_stock_data(symbol, start_date, end_date, interval=timeframe)