with open('bot.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')  # strip BOM otomatis
lines = c.split('\n')

# Hapus \r dari semua lines
lines = [l.rstrip('\r') for l in lines]

# Cek sekitar line 279-281
for i in range(277, 285):
    print(i, repr(lines[i]))
