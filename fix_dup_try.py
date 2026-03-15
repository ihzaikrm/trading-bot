with open('bot.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')
lines = c.split('\n')
lines = [l.rstrip('\r') for l in lines]

# Hapus line 280 (try: duplikat)
del lines[280]

c = '\n'.join(lines)
with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(c)

try:
    compile(c, 'bot.py', 'exec')
    print('Syntax OK!')
except SyntaxError as e:
    print('Error:', e)
