import requests

def get_smc_context(symbol="BTC"):
    try:
        url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=" + symbol + "&tsym=USD&limit=30"
        data = requests.get(url, timeout=10).json()["Data"]["Data"]
        highs  = [d["high"]  for d in data]
        lows   = [d["low"]   for d in data]
        opens  = [d["open"]  for d in data]
        closes = [d["close"] for d in data]
        n = len(data)
        findings = []

        for i in range(2, n):
            if highs[i-2] < lows[i]:
                mid = round((highs[i-2] + lows[i]) / 2, 0)
                findings.append(f"Bullish FVG di ${mid:,.0f} ({n-i} hari lalu)")
            if lows[i-2] > highs[i]:
                mid = round((lows[i-2] + highs[i]) / 2, 0)
                findings.append(f"Bearish FVG di ${mid:,.0f} ({n-i} hari lalu)")

        avg_body = sum(abs(closes[j]-opens[j]) for j in range(n)) / n
        for i in range(1, n-2):
            body = abs(closes[i] - opens[i])
            if body < avg_body * 1.5:
                continue
            if closes[i] < opens[i] and closes[i+1] > opens[i+1] and closes[i+2] > opens[i+2]:
                findings.append(f"Bullish OB di ${lows[i]:,.0f}-${highs[i]:,.0f} ({n-i} hari lalu)")
            elif closes[i] > opens[i] and closes[i+1] < opens[i+1] and closes[i+2] < opens[i+2]:
                findings.append(f"Bearish OB di ${lows[i]:,.0f}-${highs[i]:,.0f} ({n-i} hari lalu)")

        recent_high = max(highs[-6:-1])
        recent_low  = min(lows[-6:-1])
        if highs[-1] > recent_high and closes[-1] < recent_high:
            findings.append(f"Liquidity Sweep HIGH di ${recent_high:,.0f} - potensi reversal turun")
        if lows[-1] < recent_low and closes[-1] > recent_low:
            findings.append(f"Liquidity Sweep LOW di ${recent_low:,.0f} - potensi reversal naik")

        if not findings:
            return "SMC: Tidak ada zona signifikan."
        return "SMC ZONES:\n" + "\n".join(f"- {f}" for f in findings[-3:])

    except Exception as e:
        return f"SMC: error - {str(e)}"

if __name__ == "__main__":
    ctx = get_smc_context("BTC")
    print(ctx)
