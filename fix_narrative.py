with open("core/narrative_scanner.py","r",encoding="utf-8") as f: c=f.read()

old = "    if not top_narratives:\n        top_narratives = [(n,v) for n,v in top_keyword if v > 0][:3]\n        print(f\"  Top narratives (keyword fallback): {top_narratives}\")\n    else:\n        print(f\"  Top narratives: {[(n,v) for n,v in top_narratives]}\")"

new = (
    "    if not top_narratives:\n"
    "        top_narratives = [(n,v) for n,v in top_keyword if v > 0][:3]\n"
    "        print(f\"  Top narratives (keyword fallback): {top_narratives}\")\n"
    "    else:\n"
    "        print(f\"  Top narratives: {[(n,v) for n,v in top_narratives]}\")\n"
    "    # Simpan ke narrative_state.json agar dashboard bisa baca\n"
    "    import json, os\n"
    "    state_file = 'logs/narrative_state.json'\n"
    "    try:\n"
    "        existing = json.load(open(state_file)) if os.path.exists(state_file) else {}\n"
    "        existing['active_narratives'] = [[n,v] for n,v in top_narratives]\n"
    "        existing['last_scan'] = str(__import__('datetime').datetime.now())\n"
    "        json.dump(existing, open(state_file,'w'), indent=2)\n"
    "    except: pass"
)
c = c.replace(old, new, 1)
with open("core/narrative_scanner.py","w",encoding="utf-8") as f: f.write(c)
print("Narrative fix done!")
