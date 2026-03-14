import sys, os
sys.path.insert(0, os.getcwd())

c = open('bot.py', encoding='utf-8').read()

old = '    alloc = data["balance"] / len(ASSETS)'

new = '''    # ── VIX Regime Detection ──────────────────────────────
    try:
        import yfinance as yf
        vix_hist = yf.Ticker("^VIX").history(period="2d")
        vix = round(float(vix_hist["Close"].iloc[-1]), 2) if not vix_hist.empty else 20.0
    except:
        vix = 20.0

    if vix < 15:
        regime = "BULL"
        kelly_mult = 1.0
    elif vix < 25:
        regime = "NORMAL"
        kelly_mult = 0.8
    elif vix < 35:
        regime = "FEAR"
        kelly_mult = 0.5
    else:
        regime = "PANIC"
        kelly_mult = 0.0

    print(f"  VIX: {vix} | Regime: {regime} | Kelly mult: {kelly_mult}")
    if kelly_mult == 0.0:
        msg = f"⚠️ PANIC REGIME (VIX {vix}) — skip semua entry"
        print(msg); tg(msg)

    alloc = data["balance"] / len(ASSETS) * kelly_mult'''

if old in c:
    c = c.replace(old, new)
    open('bot.py', 'w', encoding='utf-8').write(c)
    print('OK: VIX regime detection ditambahkan')
else:
    print('SKIP: pattern tidak ditemukan')
    idx = c.find('alloc = data')
    print(repr(c[idx-30:idx+60]))
