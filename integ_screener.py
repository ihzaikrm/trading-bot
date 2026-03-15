with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# Tambah import screener di atas
c = c.replace(
    "from core.dxy_filter import get_dxy_signal",
    "from core.dxy_filter import get_dxy_signal\nfrom core.screener import run_screener"
, 1)

# Ganti ASSETS statis dengan dynamic dari screener
old = (
    'ASSETS = {\n'
    '\n\n\n"BTC/USDT": {"type": "crypto", "symbol": "BTC/USDT", "name": "Bitcoin"},\n'
    '\n\n\n"XAUUSD":   {"type": "stock",  "symbol": "GC=F",     "name": "Gold"},\n'
    '\n\n\n"SPX":      {"type": "stock",  "symbol": "^GSPC",    "name": "S&P 500"},\n'
    '\n\n\n}'
)
new = (
    '# === DYNAMIC ASSETS dari Screener ===\n'
    'ASSETS_BASE = {\n'
    '    "BTC/USDT": {"type": "crypto", "symbol": "BTC/USDT", "name": "Bitcoin"},\n'
    '    "XAUUSD":   {"type": "stock",  "symbol": "GC=F",     "name": "Gold"},\n'
    '    "SPX":      {"type": "stock",  "symbol": "^GSPC",    "name": "S&P 500"},\n'
    '}\n'
    '\n'
    'def build_dynamic_assets(narratives=None, balance=1000, kelly_mult=0.5):\n'
    '    """Build ASSETS dict dari screener + base assets"""\n'
    '    assets = dict(ASSETS_BASE)  # selalu include base\n'
    '    try:\n'
    '        candidates = run_screener(\n'
    '            active_narratives=narratives or ["INFLATION_HEDGE","RISK_OFF"],\n'
    '            balance=balance,\n'
    '            kelly_mult=kelly_mult\n'
    '        )\n'
    '        SYMBOL_MAP = {\n'
    '            "BTC": ("BTC/USDT","crypto","BTC/USDT","Bitcoin"),\n'
    '            "ETH": ("ETH/USDT","crypto","ETH/USDT","Ethereum"),\n'
    '            "SOL": ("SOL/USDT","crypto","SOL/USDT","Solana"),\n'
    '            "BNB": ("BNB/USDT","crypto","BNB/USDT","BNB"),\n'
    '        }\n'
    '        for c in candidates:\n'
    '            sym = c["symbol"]\n'
    '            if sym in SYMBOL_MAP:\n'
    '                key, atype, symbol, name = SYMBOL_MAP[sym]\n'
    '            else:\n'
    '                key = sym\n'
    '                atype = c["type"]\n'
    '                symbol = sym\n'
    '                name = sym\n'
    '            if key not in assets:\n'
    '                assets[key] = {\n'
    '                    "type": atype,\n'
    '                    "symbol": symbol,\n'
    '                    "name": name,\n'
    '                    "alloc": c.get("alloc", 0),\n'
    '                    "manip_score": c.get("manip_score", 0)\n'
    '                }\n'
    '        print(f"  Dynamic assets: {list(assets.keys())}")\n'
    '    except Exception as e:\n'
    '        print(f"  Screener error: {e}, using base assets")\n'
    '    return assets\n'
    '\n'
    'ASSETS = ASSETS_BASE  # fallback default'
)
c = c.replace(old, new, 1)
with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
