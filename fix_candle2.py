with open('dashboard/index.html','r',encoding='utf-8') as f: c=f.read()
lines = c.split('\n')

# Fix baris 519: ganti Kraken ke CryptoCompare (no CORS, no block)
lines[519] = "    const r = await fetch('https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=14');"
lines[520] = "    const d = await r.json();"
lines[521] = "    const raw = d.Data?.Data || [];"
lines[522] = "    return raw.map(k => ({time: k.time, open: k.open, high: k.high, low: k.low, close: k.close}));"
lines[523] = "  } catch(e) { return []; }"
lines[524] = "}"

c = '\n'.join(lines)
with open('dashboard/index.html','w',encoding='utf-8') as f: f.write(c)
print('Done! Line 519:', lines[519][:60])
