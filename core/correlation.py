# core/correlation.py
import numpy as np
from config.assets import ASSETS

# Matriks korelasi antar aset (nilai antara -1 dan 1)
# Sumber: perkiraan kasar, bisa diperbarui nanti dengan data historis
CORRELATION_MATRIX = {
    "BTC/USDT": {
        "BTC/USDT": 1.0,
        "XAUUSD": 0.3,   # Bitcoin dengan Gold (agak positif)
        "SPX": 0.4       # Bitcoin dengan S&P 500 (cukup positif)
    },
    "XAUUSD": {
        "BTC/USDT": 0.3,
        "XAUUSD": 1.0,
        "SPX": -0.2      # Gold dengan S&P 500 (sedikit negatif)
    },
    "SPX": {
        "BTC/USDT": 0.4,
        "XAUUSD": -0.2,
        "SPX": 1.0
    }
}

CORRELATION_THRESHOLD = 0.7  # Ambang batas korelasi tinggi

def get_correlation(asset1, asset2):
    """Mengembalikan korelasi antara dua aset (berdasarkan nama)"""
    if asset1 not in CORRELATION_MATRIX or asset2 not in CORRELATION_MATRIX[asset1]:
        return 0.0
    return CORRELATION_MATRIX[asset1][asset2]

def is_highly_correlated(asset1, asset2):
    """Cek apakah dua aset memiliki korelasi tinggi (mutlak)"""
    corr = get_correlation(asset1, asset2)
    return abs(corr) >= CORRELATION_THRESHOLD

def check_correlation(new_asset, current_positions):
    """
    Mengecek apakah membuka posisi pada new_asset akan berkorelasi tinggi
    dengan aset yang sudah memiliki posisi terbuka (baik long maupun short).
    Mengembalikan True jika aman (tidak konflik), False jika dilarang.
    """
    for pos_asset in current_positions:
        if is_highly_correlated(new_asset, pos_asset):
            # Jika korelasi tinggi, kita perlu periksa arah posisi
            # Idealnya, jika korelasi positif, sebaiknya tidak buka posisi searah.
            # Tapi untuk sederhana, kita larang semua jika korelasi tinggi.
            # Bisa dikembangkan lebih lanjut.
            return False
    return True