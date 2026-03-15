with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# Tambah default smc_text dan delta_text sebelum prompt dibangun
old = "        # === SMC + DELTA CONTEXT untuk LLM ==="
new = (
    "        smc_text = ''\n"
    "        delta_text = ''\n"
    "        # === SMC + DELTA CONTEXT untuk LLM ==="
)
c = c.replace(old, new, 1)

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
