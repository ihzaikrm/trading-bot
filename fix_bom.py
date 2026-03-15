# Fix BOM + rewrite blok news cache
with open('bot.py', 'rb') as f:
    raw = f.read()
if raw.startswith(b'\xef\xbb\xbf'):
    raw = raw[3:]
    print('BOM removed')
c = raw.decode('utf-8')

# Cari dan ganti blok yang rusak
old = 'import json as _json, os as _os\n_cache = _os.path.join("logs","news_cache.json")\n        try:'
new = '        import json as _json, os as _os\n        _cache = _os.path.join("logs","news_cache.json")\n        try:'
if old in c:
    c = c.replace(old, new, 1)
    print('Block fixed')
else:
    print('Pattern not found - checking lines')
    lines = c.split('\n')
    for i,l in enumerate(lines):
        if 'import json as _json' in l or '_cache = _os' in l or ('try:' in l and 270 < i < 290):
            print(i, repr(l))

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(c)

try:
    compile(c, 'bot.py', 'exec')
    print('Syntax OK!')
except SyntaxError as e:
    print('Error:', e)
