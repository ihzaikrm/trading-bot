c = open('bot.py', encoding='utf-8').read()
lines = c.split('\n')
for i,l in enumerate(lines):
    if 'import json as _json' in l:
        print(i, repr(l))
    if '_cache = _os.path' in l:
        print(i, repr(l))
    if '_news = _json' in l:
        print(i, repr(l))
    if '_titles = ' in l:
        print(i, repr(l))
    if 'news_text_for_narr = " ".join(_titles)' in l:
        print(i, repr(l))
    if "except:" in l and i > 270 and i < 290:
        print(i, repr(l))
