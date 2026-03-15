with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# Hapus global ASSETS yang error
c = c.replace(
    "    # === BUILD DYNAMIC ASSETS dari screener ===\n    global ASSETS\n    try:\n",
    "    # === BUILD DYNAMIC ASSETS dari screener ===\n    try:\n",
1)

# Ganti ASSETS = ... di dalam try block dengan ACTIVE_ASSETS
c = c.replace(
    '        ASSETS = build_dynamic_assets(active_narr, data["balance"], kelly_mult)\n'
    '        print(f"  Total aset aktif: {len(ASSETS)}")\n'
    '    except Exception as e:\n'
    '        print(f"  Dynamic assets error: {e}")\n'
    '        ASSETS = ASSETS_BASE\n',
    '        ACTIVE_ASSETS = build_dynamic_assets(active_narr, data["balance"], kelly_mult)\n'
    '        print(f"  Total aset aktif: {len(ACTIVE_ASSETS)}")\n'
    '    except Exception as e:\n'
    '        print(f"  Dynamic assets error: {e}")\n'
    '        ACTIVE_ASSETS = ASSETS_BASE\n',
1)

# Ganti semua penggunaan ASSETS di dalam main() dengan ACTIVE_ASSETS
# Tapi hanya di dalam fungsi main, bukan definisi awal
c = c.replace(
    'alloc = data["balance"] / max(len(ASSETS), 1) * kelly_mult',
    'alloc = data["balance"] / max(len(ACTIVE_ASSETS), 1) * kelly_mult'
)
c = c.replace(
    'for name, info in ASSETS.items():',
    'for name, info in ACTIVE_ASSETS.items():'
)
c = c.replace(
    'result = get_asset_data(name, ASSETS.get(name, {"type":"stock","symbol":name}))',
    'result = get_asset_data(name, ACTIVE_ASSETS.get(name, {"type":"stock","symbol":name}))'
)

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
