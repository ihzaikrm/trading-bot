with open("dashboard/index.html","r",encoding="utf-8") as f: c=f.read()

old = "  const candles = data.map(d => ({\n    time: Math.floor(d[0] / 1000),\nopen: parseFloat(d[1]), high: parseFloat(d[2]), low: parseFloat(d[3]), close: parseFloat(d[4])\n  }));"
new = "  const candles = data.map(d => ({\n    time: d.time,\n    open: parseFloat(d.open), high: parseFloat(d.high), low: parseFloat(d.low), close: parseFloat(d.close)\n  }));"

if old in c:
    c = c.replace(old, new, 1)
    print("Fixed!")
else:
    print("NOT FOUND")

with open("dashboard/index.html","w",encoding="utf-8") as f: f.write(c)
