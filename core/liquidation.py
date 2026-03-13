# core/liquidation.py
import math
from config.trading_params import LEVERAGE

def calculate_liquidation_price(entry_price, position_type, margin, leverage=LEVERAGE):
    """
    Hitung harga likuidasi untuk posisi long atau short.
    Asumsi: maintenance margin = 0.5% (dapat disesuaikan).
    Rumus sederhana: harga likuidasi = entry_price * (1 - 1/leverage) untuk long,
    dan entry_price * (1 + 1/leverage) untuk short.
    """
    maintenance = 0.005  # 0.5% maintenance margin
    if position_type == "long":
        # Harga turun sampai (entry - entry/leverage) ≈ likuidasi
        liquidation = entry_price * (1 - 1/leverage + maintenance)
    else:  # short
        liquidation = entry_price * (1 + 1/leverage - maintenance)
    return round(liquidation, 2)

def check_margin_call(equity, balance, positions, shorts, current_prices):
    """
    Periksa apakah ada posisi yang mendekati likuidasi.
    Jika equity < 10% dari balance awal, kirim peringatan.
    """
    total_margin = 0
    for sym, pos in positions.items():
        if sym in current_prices:
            price = current_prices[sym]
            # Hitung margin digunakan (asumsi)
            margin_used = pos['amount']  # amount adalah modal yang digunakan
            total_margin += margin_used
    for sym, pos in shorts.items():
        if sym in current_prices:
            margin_used = pos['amount']
            total_margin += margin_used

    if total_margin == 0:
        return None

    # Jika equity di bawah 10% dari total margin, anggap margin call
    if equity < 0.1 * total_margin:
        return "⚠️ MARGIN CALL: Equity sangat rendah! Segera evaluasi posisi."
    return None