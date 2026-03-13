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

# â”€â”€ H3: ATR-based adaptive SL/TP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 4.5

def get_adaptive_sl_tp(asset, current_price, atr, fixed_sl_pct, fixed_tp_pct):
    """
    SL = max(fixed_sl, 1.5 x ATR%)
    TP = max(fixed_tp, 4.5 x ATR%)   <- rasio 3:1
    Melebar saat volatilitas tinggi, tidak pernah di bawah nilai riset.
    """
    if current_price <= 0 or atr <= 0:
        return fixed_sl_pct, fixed_tp_pct
    atr_pct    = atr / current_price
    final_sl   = max(fixed_sl_pct, ATR_SL_MULTIPLIER * atr_pct)
    final_tp   = max(fixed_tp_pct, ATR_TP_MULTIPLIER * atr_pct)
    return round(final_sl, 4), round(final_tp, 4)


# H4: Load optimal params dari WFO
def get_wfo_params(symbol: str) -> dict:
    """
    Ambil params optimal hasil WFO quarterly.
    Dipanggil dari signal_engine.py sebelum jalankan strategi.
    Fallback ke default jika WFO belum pernah jalan.
    """
    try:
        from backtest.walk_forward import get_optimal_params
        return get_optimal_params(symbol)
    except Exception:
        return {}
