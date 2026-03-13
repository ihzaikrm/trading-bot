# config/assets.py
# Daftar aset dengan parameter masing-masing
# ✅ SL/TP diverifikasi dari 300+ backtest (3x leverage, 2015-2024)
# Insight kunci: TP=30% (WIDE) SELALU menang — letting profits run
#
# BTC:  SL=6%  TP=30% → CAGR 197.5% ✅ (vs SL=5% TP=10% → hanya 17.0%)
# Gold: SL=8%  TP=30% → Smart Hold  ✅ (exit timing, bukan entry timing)
# SPX:  SL=10% TP=30% → CAGR 28.0%  ✅ (vs SL=4% TP=5%  → hanya 5.0%)

ASSETS = {
    "BTC/USDT": {
        "type": "crypto",
        "symbol": "BTC/USDT",
        "name": "Bitcoin",
        "sl_pct": 6.0,   # ✅ was 5.0 (AI lain) → riset: 6.0
        "tp_pct": 30.0,  # ✅ was 10.0 (AI lain) → riset: 30.0
    },
    "XAUUSD": {
        "type": "stock",
        "symbol": "GC=F",
        "name": "Gold",
        "sl_pct": 8.0,   # ✅ was 5.0 (AI lain) → riset: 8.0
        "tp_pct": 30.0,  # ✅ was 10.0 (AI lain) → riset: 30.0
    },
    "SPX": {
        "type": "stock",
        "symbol": "^GSPC",
        "name": "S&P 500",
        "sl_pct": 10.0,  # ✅ was 4.0 (AI lain) → riset: 10.0
        "tp_pct": 30.0,  # ✅ was 5.0 (AI lain) → riset: 30.0
    },
}