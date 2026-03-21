"""
Performance Improvements Module
1. Fear & Greed Index (alternative.me - gratis)
2. Trailing Stop Loss
3. Correlation Filter
"""
import requests, json, os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============================================================
# 1. FEAR & GREED INDEX
# ============================================================
def get_fear_greed():
    """Ambil Fear & Greed Index dari alternative.me (gratis, unlimited)"""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=7", timeout=10)
        data = r.json()["data"]
        current = data[0]
        value = int(current["value"])
        label = current["value_classification"]
        # Trend: naik atau turun dalam 7 hari
        week_avg = sum(int(d["value"]) for d in data) / len(data)
        trend = "IMPROVING" if value > week_avg else "DECLINING"
        return {
            "value": value,
            "label": label,
            "trend": trend,
            "week_avg": round(week_avg, 1),
            "signal_modifier": _fg_signal_modifier(value)
        }
    except Exception as e:
        print(f"  Fear & Greed error: {e}")
        return {"value": 50, "label": "Neutral", "trend": "STABLE",
                "week_avg": 50, "signal_modifier": 1.0}

def _fg_signal_modifier(value):
    """
    Modifier untuk confidence sinyal berdasarkan F&G:
    - Extreme Fear (0-25): BUY lebih agresif (contrarian), SELL lebih konservatif
    - Fear (25-45): slight BUY bias
    - Neutral (45-55): normal
    - Greed (55-75): slight SELL bias
    - Extreme Greed (75-100): SELL lebih agresif, BUY lebih konservatif
    """
    if value <= 25:   return 1.3   # Extreme Fear = BUY opportunity
    elif value <= 45: return 1.1   # Fear = slight BUY bias
    elif value <= 55: return 1.0   # Neutral
    elif value <= 75: return 0.9   # Greed = slight SELL bias
    else:             return 0.7   # Extreme Greed = caution!

def apply_fg_to_signal(signal, confidence, fg_data):
    """Apply F&G modifier ke confidence sinyal"""
    modifier = fg_data["signal_modifier"]
    fg_value = fg_data["value"]
    if signal == "BUY":
        new_conf = min(1.0, confidence * modifier)
    elif signal == "SELL":
        new_conf = min(1.0, confidence * (2.0 - modifier))
    else:
        new_conf = confidence
    return round(new_conf, 3)

# ============================================================
# 2. TRAILING STOP LOSS
# ============================================================
TRAILING_FILE = "logs/trailing_stops.json"

def load_trailing_stops():
    if os.path.exists(TRAILING_FILE):
        with open(TRAILING_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_trailing_stops(data):
    os.makedirs("logs", exist_ok=True)
    with open(TRAILING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def update_trailing_stop(asset, current_price, position, trailing_pct=0.08):
    """
    Update trailing stop untuk posisi terbuka.
    trailing_pct = 8% di bawah high tertinggi sejak entry
    Returns: (stop_price, should_sell)
    """
    stops = load_trailing_stops()
    entry_price = position.get("entry_price", current_price)
    pnl_pct = (current_price - entry_price) / entry_price

    if asset not in stops:
        stops[asset] = {
            "highest_price": current_price,
            "stop_price": current_price * (1 - trailing_pct),
            "entry_price": entry_price,
            "activated": False
        }

    stop_data = stops[asset]

    # Aktifkan trailing stop setelah profit > 5%
    if pnl_pct >= 0.05:
        stop_data["activated"] = True

    # Update highest price
    if current_price > stop_data["highest_price"]:
        stop_data["highest_price"] = current_price
        stop_data["stop_price"] = current_price * (1 - trailing_pct)

    stops[asset] = stop_data
    save_trailing_stops(stops)

    # Cek apakah harga sudah turun ke bawah trailing stop
    should_sell = (stop_data["activated"] and
                   current_price <= stop_data["stop_price"])

    return round(stop_data["stop_price"], 2), should_sell

def clear_trailing_stop(asset):
    """Hapus trailing stop saat posisi ditutup"""
    stops = load_trailing_stops()
    if asset in stops:
        del stops[asset]
        save_trailing_stops(stops)

# ============================================================
# 3. CORRELATION FILTER
# ============================================================
def get_correlation_matrix(assets_data):
    """
    Hitung korelasi antar aset dari data historis.
    assets_data: {asset_name: [list of closing prices]}
    Returns: correlation matrix sebagai dict
    """
    if not assets_data or len(assets_data) < 2:
        return {}
    df = pd.DataFrame(assets_data)
    # Pastikan semua kolom sama panjang
    min_len = min(len(v) for v in assets_data.values())
    df = pd.DataFrame({k: v[-min_len:] for k, v in assets_data.items()})
    corr = df.corr()
    return corr.to_dict()

def is_too_correlated(new_asset, existing_positions, historical_prices, threshold=0.80):
    """
    Cek apakah aset baru terlalu berkorelasi dengan posisi yang sudah ada.
    threshold: 0.80 = korelasi > 80% dianggap terlalu tinggi
    Returns: (bool, list of correlated assets)
    """
    if not existing_positions or not historical_prices:
        return False, []

    assets_to_check = list(existing_positions.keys()) + [new_asset]
    available = {a: historical_prices[a] for a in assets_to_check
                 if a in historical_prices}

    if len(available) < 2 or new_asset not in available:
        return False, []

    corr_matrix = get_correlation_matrix(available)
    if not corr_matrix or new_asset not in corr_matrix:
        return False, []

    highly_correlated = []
    for existing in existing_positions:
        if existing in corr_matrix.get(new_asset, {}):
            corr_val = abs(corr_matrix[new_asset][existing])
            if corr_val >= threshold:
                highly_correlated.append((existing, round(corr_val, 3)))

    return len(highly_correlated) > 0, highly_correlated

def get_diversification_score(positions, historical_prices):
    """
    Skor diversifikasi portofolio (0-100).
    100 = sempurna terdiversifikasi, 0 = semua aset bergerak bersamaan
    """
    if len(positions) < 2:
        return 100

    assets = list(positions.keys())
    available = {a: historical_prices[a] for a in assets if a in historical_prices}

    if len(available) < 2:
        return 100

    corr_matrix = get_correlation_matrix(available)
    if not corr_matrix:
        return 100

    # Hitung rata-rata korelasi antar semua pasang aset
    corr_values = []
    for i, a1 in enumerate(available):
        for a2 in list(available.keys())[i+1:]:
            if a2 in corr_matrix.get(a1, {}):
                corr_values.append(abs(corr_matrix[a1][a2]))

    if not corr_values:
        return 100

    avg_corr = sum(corr_values) / len(corr_values)
    score = round((1 - avg_corr) * 100, 1)
    return score

# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("=== PERFORMANCE IMPROVEMENTS TEST ===\n")

    # Test 1: Fear & Greed
    print("[1] Fear & Greed Index:")
    fg = get_fear_greed()
    print(f"  Value: {fg['value']} ({fg['label']})")
    print(f"  Trend: {fg['trend']} | 7-day avg: {fg['week_avg']}")
    print(f"  Signal modifier: {fg['signal_modifier']}x")

    # Contoh apply ke sinyal
    test_signal = "BUY"
    test_conf = 0.65
    new_conf = apply_fg_to_signal(test_signal, test_conf, fg)
    print(f"  BUY conf {test_conf} ? {new_conf} (after F&G)")

    # Test 2: Trailing Stop
    print("\n[2] Trailing Stop Loss:")
    mock_position = {"entry_price": 70000, "qty": 0.005, "amount": 350}
    # Simulasi harga naik lalu turun
    prices = [70000, 72000, 75000, 74000, 73000, 71500]
    for price in prices:
        stop, sell = update_trailing_stop("BTC/USDT", price, mock_position)
        print(f"  Price: ${price:,} | Stop: ${stop:,} | SELL: {sell}")
    clear_trailing_stop("BTC/USDT")

    # Test 3: Correlation
    print("\n[3] Correlation Filter:")
    mock_prices = {
        "BTC/USDT": [68000,69000,70000,71000,70500,71500,72000],
        "ETH/USDT": [3400,3450,3500,3550,3525,3575,3600],
        "GC=F":     [2900,2910,2905,2920,2915,2925,2930],
    }
    existing = {"BTC/USDT": mock_position}
    too_corr, corr_list = is_too_correlated("ETH/USDT", existing, mock_prices)
    print(f"  ETH vs BTC: too correlated = {too_corr} | {corr_list}")
    too_corr2, corr_list2 = is_too_correlated("GC=F", existing, mock_prices)
    print(f"  Gold vs BTC: too correlated = {too_corr2} | {corr_list2}")
    div_score = get_diversification_score(existing, mock_prices)
    print(f"  Diversification score: {div_score}/100")

    print("\n? Semua test selesai!")
