with open("dashboard/index.html","r",encoding="utf-8") as f: c=f.read()

# Revert ke Unix timestamp langsung - LightweightCharts menerima ini
old = "return raw.map(k => ({time: new Date(k.time*1000).toISOString().split('T')[0], open: k.open, high: k.high, low: k.low, close: k.close"
new = "return raw.map(k => ({time: k.time, open: k.open, high: k.high, low: k.low, close: k.close"

c = c.replace(old, new, 1)
with open("dashboard/index.html","w",encoding="utf-8") as f: f.write(c)
print("Done!")
