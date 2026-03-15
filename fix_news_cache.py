c = open('bot.py', encoding='utf-8').read()

old = 'news_text_for_narr = " ".join([a.get("title","") for a in data.get("news",[])[:5]]) if "news" in data else ""'

new = '''# Ambil news dari cache file
import json as _json, os as _os
_cache = _os.path.join("logs","news_cache.json")
try:
            _news = _json.load(open(_cache, encoding="utf-8")) if _os.path.exists(_cache) else {}
            _titles = [a.get("title","") for a in _news.get("1h",[])[:3]] + [a.get("title","") for a in _news.get("6h",[])[:2]]
            news_text_for_narr = " ".join(_titles)
        except:
            news_text_for_narr = ""'''

if old in c:
    c = c.replace(old, new)
    open('bot.py', 'w', encoding='utf-8').write(c)
    print('OK: news_text dari cache')
else:
    print('SKIP - pattern tidak ditemukan')
