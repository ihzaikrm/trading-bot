with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# 1. Import smc_context
c = c.replace(
    "from core.dxy_filter import get_dxy_signal",
    "from core.dxy_filter import get_dxy_signal\nfrom core.smc_context import get_smc_context",
1)

# 2. Tambah SMC + Delta ke prompt LLM
old = '+news_text+"\\n\\n"'
new = (
    '+news_text+"\\n\\n"\n'
    '+smc_text+"\\n\\n"\n'
    '+delta_text+"\\n\\n"'
)
c = c.replace(old, new, 1)

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
