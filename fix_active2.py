with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# Cek nama dict yang sebenarnya ada
import re
m = re.search(r'(ASSETS\w*)\s*=\s*\{[^}]*"BTC/USDT"', c)
print("Dict name found:", m.group(1) if m else "NOT FOUND")

# Ganti ASSETS_BASE dengan ASSETS (nama asli yang pasti ada)
c = c.replace("ACTIVE_ASSETS = ASSETS_BASE  # default sebelum dynamic build",
              "ACTIVE_ASSETS = dict(ASSETS)  # default sebelum dynamic build")
c = c.replace("ACTIVE_ASSETS = ASSETS_BASE", "ACTIVE_ASSETS = dict(ASSETS)")

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
