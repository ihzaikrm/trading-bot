import yfinance as yf

def get_dxy_signal():
    """
    DXY Macro Filter:
    - DXY naik = USD kuat = bearish untuk BTC/crypto/emas
    - DXY turun = USD lemah = bullish untuk BTC/crypto/emas
    
    Return: "BULLISH", "BEARISH", "NEUTRAL" + details
    """
    try:
        dxy = yf.Ticker("DX-Y.NYB").history(period="30d")["Close"]
        if len(dxy) < 10:
            return "NEUTRAL", {"error": "data kurang"}

        current = round(float(dxy.iloc[-1]), 2)
        ma10    = round(float(dxy.tail(10).mean()), 2)
        ma20    = round(float(dxy.tail(20).mean()), 2)
        chg5d   = round((dxy.iloc[-1] - dxy.iloc[-6]) / dxy.iloc[-6] * 100, 2)

        # DXY trend
        dxy_uptrend   = current > ma10 > ma20
        dxy_downtrend = current < ma10 < ma20

        # Untuk crypto: DXY turun = BULLISH, DXY naik = BEARISH
        if dxy_downtrend and chg5d < -0.5:
            signal = "BULLISH"
        elif dxy_uptrend and chg5d > 0.5:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        details = {
            "dxy": current,
            "ma10": ma10,
            "ma20": ma20,
            "chg5d": str(chg5d) + "%",
            "trend": "DOWN" if dxy_downtrend else ("UP" if dxy_uptrend else "SIDEWAYS")
        }
        return signal, details

    except Exception as e:
        return "NEUTRAL", {"error": str(e)}


if __name__ == "__main__":
    sig, det = get_dxy_signal()
    print(f"DXY Macro Signal : {sig}")
    for k, v in det.items():
        print(f"  {k}: {v}")
