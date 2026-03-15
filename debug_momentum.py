import requests

url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=220"
data = requests.get(url, timeout=10).json()["Data"]["Data"]
closes = [d["close"] for d in data]
opens  = [d["open"]  for d in data]
vols   = [d["volumefrom"] for d in data]
print(f"Data: {len(closes)} candles")

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
sig_vals = ema([macd_line[i] for i in valid_idx], 9)
macd_sig = [None] * len(closes)
for j, i in enumerate(valid_idx):
    if sig_vals[j] is not None:
        macd_sig[i] = sig_vals[j]

ema50  = ema(closes, 50)
ema200 = ema(closes, 200)

i = len(closes) - 1
print(f"len closes={len(closes)}, i={i}")
print(f"rsi[i]={rsi_vals[i]}")
print(f"macd[i]={macd_line[i]}, macd[i-1]={macd_line[i-1]}")
print(f"sig[i]={macd_sig[i]}, sig[i-1]={macd_sig[i-1]}")
print(f"ema50[i]={ema50[i]}, ema200[i]={ema200[i]}")
print(f"delta[i]={delta[i]}, delta[i-3]={delta[i-3]}")
