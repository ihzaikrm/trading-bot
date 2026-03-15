with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# Panggil build_dynamic_assets di awal main() setelah load narratives
old = '    alloc = data["balance"] / len(ASSETS) * kelly_mult'
new = (
    '    # === BUILD DYNAMIC ASSETS dari screener ===\n'
    '    try:\n'
    '        active_narr = []\n'
    '        import json as _json\n'
    '        if os.path.exists("logs/narrative_state.json"):\n'
    '            ns = _json.load(open("logs/narrative_state.json"))\n'
    '            active_narr = [n["name"] for n in ns.get("active_narratives",[])[:3]]\n'
    '        ASSETS = build_dynamic_assets(active_narr, data["balance"], kelly_mult)\n'
    '        print(f"  Total aset aktif: {len(ASSETS)}")\n'
    '    except Exception as e:\n'
    '        print(f"  Dynamic assets error: {e}")\n'
    '        ASSETS = ASSETS_BASE\n'
    '\n'
    '    alloc = data["balance"] / max(len(ASSETS), 1) * kelly_mult'
)
c = c.replace(old, new, 1)
with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
