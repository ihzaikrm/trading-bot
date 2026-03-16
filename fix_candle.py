with open("dashboard/index.html","r",encoding="utf-8") as f: c=f.read()

old = (
    "const candles = data.map(d => ({\n"
    "time: Math.floor(d[0] / 1000),\n"
    "open: parseFloat(d[1]), high: parseFloat(d[2]), low: parseFloat(d[3]), close: parseFloat(d"
)
new = (
    "const candles = data.map(d => ({\n"
    "time: d.time,\n"
    "open: parseFloat(d.open), high: parseFloat(d.high), low: parseFloat(d.low), close: parseFloat(d.close"
)
c = c.replace(old, new, 1)
with open("dashboard/index.html","w",encoding="utf-8") as f: f.write(c)
print("Done!" if old in open("dashboard/index.html","r",encoding="utf-8").read() == False else "Check manually")
