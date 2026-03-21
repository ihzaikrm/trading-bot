# core/kelly.py
# Kelly Criterion Position Sizing
# Menghitung % balance optimal per trade untuk maksimalkan growth tanpa ruin
#
# Formula Kelly:
#   f* = (b*p - q) / b
#   b = reward/risk ratio (TP/SL)
#   p = win rate (probabilitas menang)
#   q = 1 - p (probabilitas kalah)
#
# Kita pakai Half-Kelly (f*/2) untuk safety margin — standar industri.
# Full Kelly secara teoritis optimal tapi drawdown bisa sangat dalam di bad streak.
#
# Contoh BTC (winrate 41%, SL=6%, TP=30%):
#   b = 30/6 = 5.0
#   f* = (5.0 * 0.41 - 0.59) / 5.0 = 0.293 = 29.3%
#   Half-Kelly = 14.6% per trade
#   → Jauh lebih konservatif dari 100%, drawdown jauh berkurang

import json
import os
import logging

logger = logging.getLogger(__name__)

# Default winrate per aset (dari backtest 2015-2024)
# Akan di-override secara dinamis dari logs/paper_trades.json
DEFAULT_WINRATES = {
    "BTC/USDT": 0.41,   # Vol-TSMOM backtest
    "XAUUSD":   0.33,   # Smart Hold backtest
    "SPX":      0.55,   # Monthly Seasonal backtest
}

# Batas atas/bawah Kelly untuk safety
MIN_KELLY = 0.05   # minimum 5% per trade
MAX_KELLY = 0.50   # maksimum 50% per trade (hindari over-concentration)
HALF_KELLY = True  # gunakan Half-Kelly (lebih aman)


def calc_kelly(win_rate: float, tp_pct: float, sl_pct: float) -> float:
    """
    Hitung Kelly fraction optimal.

    Args:
        win_rate: probabilitas menang (0.0 - 1.0)
        tp_pct:   take profit % (misal 30.0)
        sl_pct:   stop loss % (misal 6.0)

    Returns:
        Kelly fraction (0.0 - 1.0) yang sudah di-clamp dan di-half
    """
    if sl_pct <= 0 or tp_pct <= 0:
        return MIN_KELLY

    b = tp_pct / sl_pct       # reward/risk ratio
    p = win_rate
    q = 1.0 - p

    # Kelly formula
    kelly = (b * p - q) / b

    # Kelly negatif = edge negatif = jangan trade
    if kelly <= 0:
        logger.warning(f"Kelly negatif ({kelly:.3f}) — edge negatif, skip trade")
        return 0.0

    # Half-Kelly untuk safety
    if HALF_KELLY:
        kelly = kelly / 2.0

    # Clamp ke range yang aman
    kelly = max(MIN_KELLY, min(MAX_KELLY, kelly))

    return round(kelly, 4)


def get_live_winrate(asset_name: str, min_trades: int = 10) -> float:
    """
    Ambil win rate aktual dari logs/paper_trades.json.
    Jika data tidak cukup, fallback ke default.

    Args:
        asset_name: nama aset (BTC/USDT, XAUUSD, SPX)
        min_trades: minimum trade yang dibutuhkan untuk pakai live winrate

    Returns:
        win rate (0.0 - 1.0)
    """
    trades_file = os.path.join("logs", "paper_trades.json")

    try:
        if not os.path.exists(trades_file):
            return DEFAULT_WINRATES.get(asset_name, 0.40)

        with open(trades_file, "r") as f:
            data = json.load(f)

        history = data.get("history", [])

        # Filter trade yang sudah ditutup untuk aset ini
        closed = [
            t for t in history
            if t.get("asset") == asset_name
            and t.get("status") == "closed"
            and t.get("pnl") is not None
        ]

        if len(closed) < min_trades:
            logger.info(
                f"[Kelly] {asset_name}: hanya {len(closed)} trade closed "
                f"(min {min_trades}), pakai default winrate"
            )
            return DEFAULT_WINRATES.get(asset_name, 0.40)

        wins = sum(1 for t in closed if t["pnl"] > 0)
        live_wr = wins / len(closed)

        logger.info(
            f"[Kelly] {asset_name}: live winrate {live_wr:.1%} "
            f"dari {len(closed)} trades"
        )
        return live_wr

    except Exception as e:
        logger.error(f"[Kelly] Error baca paper_trades.json: {e}")
        return DEFAULT_WINRATES.get(asset_name, 0.40)


def get_position_size(asset_name: str, tp_pct: float, sl_pct: float,
                      balance: float) -> dict:
    """
    Hitung position size optimal menggunakan Kelly Criterion.

    Args:
        asset_name: nama aset
        tp_pct:     take profit % dari config/assets.py
        sl_pct:     stop loss % dari config/assets.py
        balance:    total balance saat ini

    Returns:
        dict dengan:
          - kelly_fraction: % balance yang digunakan (0.0-1.0)
          - margin:         modal yang dikunci ($)
          - kelly_pct:      dalam % untuk display
          - win_rate:       win rate yang dipakai
          - edge:           expected value per trade
    """
    win_rate = get_live_winrate(asset_name)
    kelly    = calc_kelly(win_rate, tp_pct, sl_pct)

    margin   = balance * kelly
    b        = tp_pct / sl_pct if sl_pct > 0 else 0
    edge     = (b * win_rate) - (1 - win_rate)   # expected value

    result = {
        "kelly_fraction": kelly,
        "margin":         round(margin, 2),
        "kelly_pct":      round(kelly * 100, 1),
        "win_rate":       round(win_rate, 4),
        "b_ratio":        round(b, 2),
        "edge":           round(edge, 4),
        "half_kelly":     HALF_KELLY,
    }

    logger.info(
        f"[Kelly] {asset_name}: WR={win_rate:.1%}, b={b:.1f}, "
        f"Kelly={kelly:.1%} → margin=${margin:.2f} "
        f"(edge={edge:.3f})"
    )

    return result


def kelly_summary() -> str:
    """Generate ringkasan Kelly untuk semua aset (untuk Telegram /strategy)."""
    from config.assets import ASSETS

    lines = ["📐 *KELLY CRITERION POSITION SIZING*", ""]
    lines.append(f"Mode: {'Half-Kelly' if HALF_KELLY else 'Full-Kelly'} | "
                 f"Min: {MIN_KELLY*100:.0f}% | Max: {MAX_KELLY*100:.0f}%")
    lines.append("")

    for name, info in ASSETS.items():
        sl  = info["sl_pct"]
        tp  = info["tp_pct"]
        wr  = get_live_winrate(name)
        k   = calc_kelly(wr, tp, sl)
        b   = tp / sl
        edge = (b * wr) - (1 - wr)

        status = "✅" if edge > 0 else "❌ Edge negatif"
        lines.append(
            f"{name}: WR={wr:.0%} | b={b:.1f}x | "
            f"Kelly={k*100:.1f}% {status}"
        )

    lines.append("")
    lines.append("_Ukuran posisi disesuaikan otomatis setiap trade_")
    return "\n".join(lines)
