with open("dashboard/index.html","r",encoding="utf-8") as f: c=f.read()

# Ganti CoinGecko (CORS blocked) ke CryptoCompare (CORS allowed)
old = "const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true');"
new = "const r = await fetch('https://min-api.cryptocompare.com/data/pricemultifull?fsyms=BTC,ETH&tsyms=USD');"
c = c.replace(old, new, 1)

# Fix parsing - CryptoCompare format berbeda
old2 = "    if (d.bitcoin) { p.BTC = d.bitcoin.usd; p.BTC_CHG = d.bitcoin.usd_24h_change; }"
new2 = "    if (d.RAW?.BTC?.USD) { p.BTC = d.RAW.BTC.USD.PRICE; p.BTC_CHG = d.RAW.BTC.USD.CHANGEPCT24HOUR; }"
c = c.replace(old2, new2, 1)

old3 = "    if (d.ethereum) { p.ETH = d.ethereum.usd; p.ETH_CHG = d.ethereum.usd_24h_change; }"
new3 = "    if (d.RAW?.ETH?.USD) { p.ETH = d.RAW.ETH.USD.PRICE; p.ETH_CHG = d.RAW.ETH.USD.CHANGEPCT24HOUR; }"
c = c.replace(old3, new3, 1)

with open("dashboard/index.html","w",encoding="utf-8") as f: f.write(c)
print("Done!")
