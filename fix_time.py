with open("dashboard/index.html","r",encoding="utf-8") as f: c=f.read()

old = "return raw.map(k => ({time: k.time, open: k.open, high: k.high, low: k.low, close: k.close"
new = "return raw.map(k => ({time: new Date(k.time*1000).toISOString().slice(0,10), open: k.open, high: k.high, low: k.low, close: k.close"

if old in c:
    c = c.replace(old, new, 1)
    print("Fixed!")
else:
    print("Pattern not found - cek manual")
    
with open("dashboard/index.html","w",encoding="utf-8") as f: f.write(c)
