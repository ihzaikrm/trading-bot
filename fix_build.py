with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# Hapus import duplikat
c = c.replace(
    "from core.screener import run_screener\nfrom core.screener import run_screener",
    "from core.screener import run_screener",
1)

# Tambah fungsi build_dynamic_assets setelah ASSETS dict
old = 'ASSETS = dict(ASSETS)  # fallback default'
if old not in c:
    # Cari penutup ASSETS dict dan tambah fungsi setelahnya
    # Tambah sebelum baris "async def main"
    func = (
        "\n\ndef build_dynamic_assets(narratives=None, balance=1000, kelly_mult=0.5):\n"
        "    assets = dict(ASSETS)\n"
        "    try:\n"
        "        candidates = run_screener(\n"
        "            active_narratives=narratives or ['INFLATION_HEDGE','RISK_OFF'],\n"
        "            balance=balance, kelly_mult=kelly_mult\n"
        "        )\n"
        "        SYMBOL_MAP = {\n"
        "            'BTC': ('BTC/USDT','crypto','BTC/USDT','Bitcoin'),\n"
        "            'ETH': ('ETH/USDT','crypto','ETH/USDT','Ethereum'),\n"
        "            'SOL': ('SOL/USDT','crypto','SOL/USDT','Solana'),\n"
        "        }\n"
        "        for item in candidates:\n"
        "            sym = item['symbol']\n"
        "            if sym in SYMBOL_MAP:\n"
        "                key, atype, symbol, name = SYMBOL_MAP[sym]\n"
        "            else:\n"
        "                key, atype, symbol, name = sym, item['type'], sym, sym\n"
        "            if key not in assets:\n"
        "                assets[key] = {'type': atype, 'symbol': symbol, 'name': name,\n"
        "                               'alloc': item.get('alloc',0)}\n"
        "        print(f'  Dynamic assets: {list(assets.keys())}')\n"
        "    except Exception as e:\n"
        "        print(f'  Screener error: {e}')\n"
        "    return assets\n"
    )
    c = c.replace("async def main():", func + "async def main():", 1)

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
