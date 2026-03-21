import requests

def get_momentum_signal(symbol="BTC"):
    try:
        url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=" + symbol + "&tsym=USD&limit=220"
        data = requests.get(url, timeout=10).json()["Data"]["Data"]
        closes = [d["close"] for d in data]
        opens  = [d["open"]  for d in data]
        vols   = [d["volumefrom"] for d in data]

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

        cum, delta = 0, []
        for o, c, v in zip(opens, closes, vols):
            cum += v if c >= o else -v
            delta.append(cum)

        rsi_vals = rsi(closes)
        e12 = ema(closes, 12)
        e26 = ema(closes, 26)
        macd_line = [None if e12[i] is None or e26[i] is None else e12[i]-e26[i] for i in range(len(closes))]
        valid_idx = [i for i,v in enumerate(macd_line) if v is not None]
        sig_vals  = ema([macd_line[i] for i in valid_idx], 9)
        macd_sig  = [None] * len(closes)
        for j, idx in enumerate(valid_idx):
            if sig_vals[j] is not None:
                macd_sig[idx] = sig_vals[j]

        ema50  = ema(closes, 50)
        ema200 = ema(closes, 200)

        # Pakai index terpendek agar tidak out of range
        n = min(len(closes), len(rsi_vals), len(macd_line), len(macd_sig), len(ema50), len(ema200), len(delta))
        i  = n - 1
        ip = n - 2  # previous candle

        r    = rsi_vals[i]
        m    = macd_line[i]
        s    = macd_sig[i]
        mp   = macd_line[ip]
        sp   = macd_sig[ip]
        e50  = ema50[i]
        e200 = ema200[i]
        d_now = delta[i]
        d_3   = delta[i-3]

        if None in [r, m, s, mp, sp, e50, e200]:
            return "NEUTRAL", {"reason": "indicator not ready"}

        in_uptrend = e50 > e200
        rsi_zone   = 45 < r < 65
        macd_bull  = mp < sp and m > s
        macd_bear  = mp > sp and m < s
        delta_bull = d_now > d_3
        delta_bear = d_now < d_3

        details = {
            "rsi": round(r, 1),
            "ema50_gt_200": in_uptrend,
            "delta_bullish": delta_bull,
            "macd_cross": "BULL" if macd_bull else ("BEAR" if macd_bear else "NONE"),
            "price": closes[i]
        }

        if in_uptrend and rsi_zone and macd_bull and delta_bull:
            return "BULLISH", details
        elif macd_bear and delta_bear:
            return "BEARISH", details
        else:
            return "NEUTRAL", details

    except Exception as e:
        return "NEUTRAL", {"error": str(e)}

if __name__ == "__main__":
    sig, det = get_momentum_signal("BTC")
    print(f"Momentum Signal : {sig}")
    for k, v in det.items():
        print(f"  {k}: {v}")
