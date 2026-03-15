c = open('bot.py', encoding='utf-8').read()
lines = c.split('\n')
lines[277] = '        import json as _json, os as _os'
lines[278] = '        _cache = _os.path.join("logs","news_cache.json")'
lines.insert(279, '        try:')
c = '\n'.join(lines)
open('bot.py', 'w', encoding='utf-8').write(c)
try:
    compile(c, 'bot.py', 'exec')
    print('Syntax OK!')
except SyntaxError as e:
    print('Error:', e)
