import re

# Fix 1: JSON parser di narrative_scanner.py (handle `json wrapper)
c = open('core/narrative_scanner.py', encoding='utf-8').read()
old = '''                  try:'''
new = '''                  try:
                      resp = re.sub(r'^`json\s*|`\s*$', '', resp.strip())'''
if old in c:
    c = c.replace(old, new, 1)
    open('core/narrative_scanner.py', 'w', encoding='utf-8').write(c)
    print('OK: JSON strip fix narrative_scanner')
else:
    print('SKIP narrative_scanner (cek manual)')

# Fix 2: news_summary scope di bot.py
c2 = open('bot.py', encoding='utf-8').read()
old2 = 'narrative_state = await run_narrative_scan(news_summary if "news_summary" in dir() else "", market_ctx)'
new2 = '''news_text_for_narr = " ".join([a.get("title","") for a in data.get("news",[])[:5]]) if "news" in data else ""
        narrative_state = await run_narrative_scan(news_text_for_narr, market_ctx)'''
if old2 in c2:
    c2 = c2.replace(old2, new2)
    open('bot.py', 'w', encoding='utf-8').write(c2)
    print('OK: news_summary scope fix bot.py')
else:
    print('SKIP bot.py scope fix')
