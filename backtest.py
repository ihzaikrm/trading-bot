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
