import requests, json
from datetime import datetime

url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=2000"
data = requests.get(url).json()["Data"]["Data"]
closes = [d["close"] for d in data]
opens  = [d["open"]  for d in data]
vols   = [d["volumefrom"] for d in data]
print(f"Data: {len(closes)} hari | ${closes[0]:,.0f} -> ${closes[-1]:,.0f}")

def cum_delta(opens, closes, vols):
    deltas, cum = [], 0
    for o, c, v in zip(opens, closes, vols):
        cum += v if c >= o else -v
        deltas.append(cum)
    return deltas

def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    result = [None] * period
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * 13 + gains[i]) / 14
        avg_l = (avg_l * 13 + losses[i]) / 14
        rs = avg_g / avg_l if avg_l != 0 else 100
        result.append(100 - 100 / (1 + rs))
    return result

def ema(prices, period):
    result = [None] * (period - 1)
    k = 2 / (period + 1)
    e = sum(prices[:period]) / period
    result.append(e)
    for p in prices[period:]:
        e = p * k + e * (1 - k)
        result.append(e)
    return result

def macd(prices):
    e12 = ema(prices, 12)
    e26 = ema(prices, 26)
    line = [None if e12[i] is None or e26[i] is None else e12[i] - e26[i] for i in range(len(prices))]
    valid_idx = [i for i, v in enumerate(line) if v is not None]
    sig_vals = ema([line[i] for i in valid_idx], 9)
    signal = [None] * len(prices)
    for j, i in enumerate(valid_idx):
        if sig_vals[j] is not None:
            signal[i] = sig_vals[j]
    return line, signal

def run_backtest(rsi_lo, rsi_hi, trail_pct, delta_lookback):
    rsi_vals = rsi(closes)
    macd_line, macd_sig = macd(closes)
    delta = cum_delta(opens, closes, vols)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)
    n = min(len(closes), len(rsi_vals), len(macd_line), len(macd_sig), len(delta), len(ema50), len(ema200))
    INITIAL, balance, position, trades = 1000.0, 1000.0, None, []
    peak_price = 0
    prev_macd = None

    for i in range(200, n):
        r, m, s, price = rsi_vals[i], macd_line[i], macd_sig[i], closes[i]
        if r is None or m is None or s is None or ema50[i] is None or ema200[i] is None:
            continue
        in_uptrend = ema50[i] > ema200[i]
        delta_bull = delta[i] > delta[i-delta_lookback]
        delta_bear = delta[i] < delta[i-delta_lookback]
        macd_cross_up = prev_macd is not None and prev_macd < 0 and m > 0
        macd_cross_dn = prev_macd is not None and prev_macd > 0 and m < 0
        prev_macd = m

        entry = in_uptrend and rsi_lo < r < rsi_hi and macd_cross_up and delta_bull
        exit_sig = macd_cross_dn and delta_bear

        if position is None and entry:
            amount = balance * 0.4
            position = {"entry": price, "qty": amount/price, "amount": amount}
            balance -= amount
            peak_price = price
        elif position:
            peak_price = max(peak_price, price)
            if exit_sig or price < peak_price * (1 - trail_pct):
                pnl = (price - position["entry"]) * position["qty"]
                balance += position["amount"] + pnl
                trades.append({"entry": position["entry"], "exit": price, "pnl": round(pnl,2)})
                position = None

    if position:
        pnl = (closes[-1] - position["entry"]) * position["qty"]
        balance += position["amount"] + pnl
        trades.append({"entry": position["entry"], "exit": closes[-1], "pnl": round(pnl,2)})

    wins = [t for t in trades if t["pnl"] > 0]
    wr = len(wins)/len(trades)*100 if trades else 0
    ret = (balance - INITIAL)/INITIAL*100
    max_dd = max(0, (INITIAL - balance)/INITIAL*100)
    return {"trades":len(trades), "wr":round(wr,1), "ret":round(ret,2), "dd":round(max_dd,1), "bal":round(balance,2)}

# Grid search parameter
print("\nGrid search sedang berjalan...")
results = []
for rsi_lo in [45, 50, 55]:
    for rsi_hi in [65, 70, 75]:
        for trail in [0.12, 0.15, 0.20]:
            for dlb in [3, 5, 7]:
                r = run_backtest(rsi_lo, rsi_hi, trail, dlb)
                if r["trades"] >= 3:
                    results.append({**r, "rsi_lo":rsi_lo, "rsi_hi":rsi_hi, "trail":trail, "dlb":dlb})

results.sort(key=lambda x: x["ret"], reverse=True)
top10 = results[:10]

print(f"\n{'='*72}")
print(f"  TOP 10 KOMBINASI PARAMETER")
print(f"{'='*72}")
print(f"{'RSI range':<12} {'Trail':>6} {'Delta LB':>9} {'Trades':>7} {'WR%':>6} {'Return%':>8} {'MaxDD%':>7} {'Balance':>9}")
print(f"{'-'*72}")
for r in top10:
    print(f"{str(r['rsi_lo'])+'-'+str(r['rsi_hi']):<12} {str(int(r['trail']*100))+'%':>6} {r['dlb']:>9} {r['trades']:>7} {r['wr']:>6} {r['ret']:>8} {r['dd']:>7} {'$'+str(r['bal']):>9}")
print(f"{'='*72}")

best = top10[0]
print(f"\nParameter terbaik:")
print(f"  RSI range    : {best['rsi_lo']}-{best['rsi_hi']}")
print(f"  Trailing stop: {int(best['trail']*100)}%")
print(f"  Delta lookback: {best['dlb']} hari")
print(f"  Return       : {best['ret']}%")
print(f"  Win Rate     : {best['wr']}%")

json.dump({"top10": top10, "timestamp": datetime.now().isoformat()},
    open("logs/backtest_results.json","w"), indent=2)
print("\nSaved to logs/backtest_results.json")

def run_backtest_strategy(rsi_lo=45, rsi_hi=65, trail_pct=0.2, delta_lookback=3):
    """
    Jalankan backtest dengan parameter yang diberikan.
    Return dict dengan 'return_pct', 'win_rate', 'max_dd', dll.
    """
    # Di sini kita bisa panggil ulang fungsi run_backtest yang sudah ada
    # Asumsi run_backtest menerima parameter dan mengembalikan dict hasil.
    # Jika di backtest.py fungsi utama adalah run_backtest (yang grid search), 
    # kita modifikasi sedikit agar bisa menerima parameter spesifik.
    # Alternatif: gunakan kode dari grid search tapi dengan parameter fixed.

    # Saya akan tuliskan ulang inti Strategy E dengan parameter dinamis
    # (ambil kode dari backtest.py yang melakukan backtest dengan satu set parameter)
    # Tapi karena kode backtest.py cukup panjang, kita bisa modifikasi fungsi run_backtest
    # agar bisa menerima parameter opsional. Namun yang lebih sederhana: kita buat fungsi terpisah.

    # Untuk sementara, kita panggil run_backtest (yang sudah ada) dengan parameter default
    # dan asumsikan ia bisa di-override.
    import requests, json
    from datetime import datetime

    # ambil data (sama seperti di backtest.py)
    url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=2000"
    data = requests.get(url).json()["Data"]["Data"]
    closes = [d["close"] for d in data]
    opens = [d["open"] for d in data]
    vols = [d["volumefrom"] for d in data]

    # hitung indikator (copy dari backtest.py)
    # ... (kode dari backtest.py)
    # ini hanya placeholder, harus diisi kode yang sama seperti di backtest.py
    # Namun karena panjang, kita bisa import kembali fungsi-fungsi dari backtest jika ada.
    # Tapi untuk sekarang, kita bisa gunakan pendekatan dengan memanggil fungsi yang sudah ada.

    # Karena kita tidak mau duplicate code, kita bisa import fungsi dari backtest
    # Tapi akan circular import. Solusi: pindahkan fungsi perhitungan ke modul terpisah.
    # Untuk sementara, kita buat wrapper sederhana: panggil backtest.run_backtest(parameter)
    # yang sudah kita modifikasi.def run_backtest_strategy(rsi_lo=45, rsi_hi=65, trail_pct=0.2, delta_lookback=3):
    """
    Run a single backtest with given parameters.
    Returns a dict with 'return_pct', 'win_rate', 'max_dd', 'total_trades', etc.
    """
    import requests
    from datetime import datetime

    # Fetch data
    url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=2000"
    data = requests.get(url).json()["Data"]["Data"]
    closes = [d["close"] for d in data]
    opens = [d["open"] for d in data]
    vols = [d["volumefrom"] for d in data]

    # --- Indicator functions ---
    def ema(prices, period):
        result = [None] * (period - 1)
        k = 2 / (period + 1)
        e = sum(prices[:period]) / period
        result.append(e)
        for p in prices[period:]:
            e = p * k + e * (1 - k)
            result.append(e)
        return result

    def rsi(prices, period=14):
        gains, losses = [], []
        for i in range(1, len(prices)):
            d = prices[i] - prices[i-1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        result = [None] * period
        avg_g = sum(gains[:period]) / period
        avg_l = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_g = (avg_g * 13 + gains[i]) / 14
            avg_l = (avg_l * 13 + losses[i]) / 14
            rs = avg_g / avg_l if avg_l != 0 else 100
            result.append(100 - 100 / (1 + rs))
        return result

    def cum_delta(opens, closes, vols):
        deltas, cum = [], 0
        for o, c, v in zip(opens, closes, vols):
            cum += v if c >= o else -v
            deltas.append(cum)
        return deltas

    def macd(prices):
        e12 = ema(prices, 12)
        e26 = ema(prices, 26)
        line = [None if e12[i] is None or e26[i] is None else e12[i] - e26[i] for i in range(len(prices))]
        valid_idx = [i for i, v in enumerate(line) if v is not None]
        sig_vals = ema([line[i] for i in valid_idx], 9)
        signal = [None] * len(prices)
        for j, i in enumerate(valid_idx):
            if sig_vals[j] is not None:
                signal[i] = sig_vals[j]
        return line, signal

    # Compute indicators
    rsi_vals = rsi(closes)
    macd_line, macd_sig = macd(closes)
    delta = cum_delta(opens, closes, vols)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)

    n = min(len(closes), len(rsi_vals), len(macd_line), len(macd_sig), len(delta), len(ema50), len(ema200))

    INITIAL = 1000.0
    balance = INITIAL
    position = None
    trades = []
    peak = 0
    prev_m = None

    for i in range(200, n):
        r = rsi_vals[i]
        m = macd_line[i]
        s = macd_sig[i]
        price = closes[i]
        if None in [r, m, s, ema50[i], ema200[i]]:
            continue
        in_up = ema50[i] > ema200[i]
        d_bull = delta[i] > delta[i - delta_lookback]
        d_bear = delta[i] < delta[i - delta_lookback]
        macd_up = prev_m is not None and prev_m < 0 and m > 0
        macd_dn = prev_m is not None and prev_m > 0 and m < 0
        prev_m = m

        if position is None and in_up and rsi_lo < r < rsi_hi and macd_up and d_bull:
            amount = balance * 0.4  # 40% allocation
            qty = amount / price
            position = {"entry": price, "qty": qty, "amount": amount}
            balance -= amount
            peak = price
        elif position:
            peak = max(peak, price)
            if (macd_dn and d_bear) or price < peak * (1 - trail_pct):
                pnl = (price - position["entry"]) * position["qty"]
                balance += position["amount"] + pnl
                trades.append(pnl)
                position = None
                peak = 0

    if position:
        pnl = (closes[-1] - position["entry"]) * position["qty"]
        balance += position["amount"] + pnl
        trades.append(pnl)

    wins = [p for p in trades if p > 0]
    total_pnl = sum(trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    return_pct = (balance - INITIAL) / INITIAL * 100
    max_dd = max(0, (INITIAL - balance) / INITIAL * 100)  # simplified

    return {
        "return_pct": round(return_pct, 2),
        "win_rate": round(win_rate, 1),
        "max_dd": round(max_dd, 1),
        "total_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "final_balance": round(balance, 2)
    }
