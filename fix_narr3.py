with open("core/narrative_scanner.py","r",encoding="utf-8") as f: c=f.read()

old = '"MARKET DATA:\\n" + market_context + "\\n\\n"'
new = '"MARKET DATA:\\n" + (str(market_context) if not isinstance(market_context,str) else market_context) + "\\n\\n"'

c = c.replace(old, new, 1)
with open("core/narrative_scanner.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
