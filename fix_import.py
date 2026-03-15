with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# Hapus import yang ada di dalam loop (di SMC+Delta block)
c = c.replace(
    "            from core.momentum_filter import get_momentum_signal\n",
    "",
1)

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
