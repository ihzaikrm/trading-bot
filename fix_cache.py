with open('bot.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')
# Fix struktur news_cache
old = '_results = _news.get("results", {}); _titles = [n.get("title","") for n in _results.get("1h",{}).get("news",[])[:3]] + [n.get("title","") for n in _results.get("6h",{}).get("news",[])[:3]]'
new = '_results = _news.get("results", {}); _1h = _results.get("1h",{}).get("news",[]); _6h = _results.get("6h",{}).get("news",[]); _titles = [n.get("title","") for n in _1h[:3]] + [n.get("title","") for n in _6h[:3]]'
if old in c:
    c = c.replace(old, new)
    print("Fixed structure!")
else:
    # Coba pattern lama
    old2 = '_titles = [a.get("title","") for a in _news.get("1h",[])[:3]] + [a.get("title","") for a in _news.get("6h",[])[:2]]'
    new2 = '_results = _news.get("results",{}); _1h = _results.get("1h",{}).get("news",[]); _6h = _results.get("6h",{}).get("news",[]); _titles = [n.get("title","") for n in _1h[:3]] + [n.get("title","") for n in _6h[:3]]'
    if old2 in c:
        c = c.replace(old2, new2)
        print("Fixed old pattern!")
    else:
        print("Pattern not found - cek manual")
        lines = c.split('\n')
        for i,l in enumerate(lines):
            if '_titles' in l and 'news' in l:
                print(i, repr(l[:100]))
with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(c)
try:
    compile(c, 'bot.py', 'exec')
    print('Syntax OK!')
except SyntaxError as e:
    print('Error:', e)
