# config/assets.py
# Daftar aset dengan parameter masing-masing
ASSETS = {
    "BTC/USDT": {
        "type": "crypto",
        "symbol": "BTC/USDT",
        "name": "Bitcoin",
        "sl_pct": 2.0,      # dari optimasi
        "tp_pct": 10.0
    },
    "XAUUSD": {
        "type": "stock",
        "symbol": "GC=F",
        "name": "Gold",
        "sl_pct": 1.0,
        "tp_pct": 8.0
    },
    "SPX": {
        "type": "stock",
        "symbol": "^GSPC",
        "name": "S&P 500",
        "sl_pct": 5.0,
        "tp_pct": 8.0
    },
}