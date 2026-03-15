with open("bot.py","r",encoding="utf-8") as f: c=f.read()

old = (
    "    # === BUILD DYNAMIC ASSETS dari screener ===\n"
    "    try:\n"
)
new = (
    "    # === BUILD DYNAMIC ASSETS dari screener ===\n"
    "    global ASSETS\n"
    "    try:\n"
)
c = c.replace(old, new, 1)
with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
