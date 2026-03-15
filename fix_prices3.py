with open('dashboard/index.html','r',encoding='utf-8') as f: c=f.read()
lines = c.split('\n')

# Fix baris 510: gold price pakai Metals.live via allorigins (no CORS)
lines[510] = "    const r3 = await fetch('https://api.metals.live/v1/spot/gold');"
lines[511] = "    const d3 = await r3.json();"
lines[512] = "    if (d3 && d3[0] && d3[0].gold) p.XAU = d3[0].gold;"

# Fix baris 519: candlestick pakai Kraken OHLC (no CORS, no rate limit)
lines[519] = "    const r = await fetch('https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1440&since=0');"
lines[520] = "    const d = await r.json();"

# Fix parsing candle untuk Kraken format
# Kraken: [time, open, high, low, close, vwap, volume, count]
lines[521] = "    const raw = Object.values(d.result).find(v => Array.isArray(v)) || [];"
lines[522] = "    return raw.slice(-14).map(k => ({time: k[0], open: parseFloat(k[1]), high: parseFloat(k[2]), low: parseFloat(k[3]), close: parseFloat(k[4])}));"

c = '\n'.join(lines)
with open('dashboard/index.html','w',encoding='utf-8') as f: f.write(c)
try:
    print('Done!')
except: pass
