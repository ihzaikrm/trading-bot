with open("bot.py","r",encoding="utf-8") as f: c=f.read()

old = '    initial = 1000.0'
new = '    ACTIVE_ASSETS = ASSETS_BASE  # default sebelum dynamic build\n    initial = 1000.0'

if old in c:
    c = c.replace(old, new, 1)
    with open("bot.py","w",encoding="utf-8") as f: f.write(c)
    print("Done!")
else:
    print("Pattern not found!")
