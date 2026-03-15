with open('dashboard/index.html','r',encoding='utf-8') as f: c=f.read()
lines = c.split('\n')
lines[522] = "    return raw.slice(-14).map(k => ({time: k[0], open: parseFloat(k[1]), high: parseFloat(k[2]), low: parseFloat(k[3]), close: parseFloat(k[4])}));"
c = '\n'.join(lines)
with open('dashboard/index.html','w',encoding='utf-8') as f: f.write(c)
print('Fixed line 522:', lines[522][:80])
