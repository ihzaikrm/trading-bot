with open("bot.py","r",encoding="utf-8") as f: c=f.read()

old = '"Balance: $"+str(round(data["balance"],2))+"\\n"'
new = (
    '"Balance: $"+str(round(data["balance"],2))+" (cash)\\n"\n'
    '+"Portfolio: $"+str(round(data["balance"]+sum((current_prices.get(s,pos["entry_price"])-pos["entry_price"])*pos["qty"]+pos["amount"] for s,pos in positions.items()),2))+"\\n"'
)
c = c.replace(old, new, 1)
with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
