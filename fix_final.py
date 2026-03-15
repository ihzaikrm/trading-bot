with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# 1. Hapus duplikat di prompt
c = c.replace(
    '+smc_text+"\\n\\n"\n+delta_text+"\\n\\n"\n+smc_text+"\\n\\n"\n+delta_text+"\\n\\n"',
    '+smc_text+"\\n\\n"\n+delta_text+"\\n\\n"',
1)

# 2. Pass smc_text dan delta_text ke pemanggilan fungsi
c = c.replace(
    'info["name"], price, change, rsi, macd_hist, macd_cross, news_text)',
    'info["name"], price, change, rsi, macd_hist, macd_cross, news_text, smc_text=smc_text, delta_text=delta_text)',
1)

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
