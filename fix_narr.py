with open("bot.py","r",encoding="utf-8") as f: c=f.read()

old = 'active_narr = [n["name"] for n in ns.get("active_narratives",[])[:3]]'
new = (
    'raw = ns.get("active_narratives",[])\n'
    '            active_narr = [n["name"] if isinstance(n,dict) else n for n in raw[:3]]'
)
c = c.replace(old, new, 1)
with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
