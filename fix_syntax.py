with open('dashboard/index.html','r',encoding='utf-8') as f: c=f.read()
lines = c.split('\n')

# Fix baris 522 - lengkapi yang terpotong
lines[522] = "    return raw.slice(-14).map(k => ({time: k[0], open: parseFloat(k[1]), high: parseFloat(k[2]), low: parseFloat(k[3]), close: parseFloat(k[4])}));"

# Fix baris 523 - tambah penutup try/catch dan fungsi
lines[523] = "  } catch(e) { return []; }"
lines.insert(524, "}")
lines.insert(525, "")

c = '\n'.join(lines)
with open('dashboard/index.html','w',encoding='utf-8') as f: f.write(c)
try:
    print('Fixed! Total lines:', len(lines))
except: pass
