c = open('bot.py', encoding='utf-8').read()

old = '    print("\\n[2] Analisa aset...")'

new = '''    # Build current_prices dict untuk narrative module
    current_prices = {}
    print("\\n[2] Analisa aset...")'''

if old in c:
    c = c.replace(old, new)
    open('bot.py', 'w', encoding='utf-8').write(c)
    print('OK: current_prices dict ditambahkan')
else:
    print('SKIP - cari pattern manual')
    idx = c.find('Analisa aset')
    print(repr(c[idx-50:idx+80]))
