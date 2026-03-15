with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# 1. Tambah parameter ke fungsi get_signal_weighted
c = c.replace(
    "async def get_signal_weighted(name, price, change, rsi, macd_hist, macd_cross, news_text):",
    "async def get_signal_weighted(name, price, change, rsi, macd_hist, macd_cross, news_text, smc_text='', delta_text=''):",
1)

# 2. Update pemanggilan fungsi di main() - tambah smc_text dan delta_text
c = c.replace(
    "signal, conf, wvotes, details, llm_signals = await get_signal_weighted(\n        smc_text = ''\n        delta_text = ''\n",
    "signal, conf, wvotes, details, llm_signals = await get_signal_weighted(\n",
1)

# Cari pemanggilan get_signal_weighted dan tambah parameter
old_call = "        signal, conf, wvotes, details, llm_signals = await get_signal_weighted(\n"
new_call = "        signal, conf, wvotes, details, llm_signals = await get_signal_weighted(\n"
# Tidak perlu ganti, parameter sudah ada default value di fungsi

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
