with open("core/narrative_scanner.py","r",encoding="utf-8") as f: c=f.read()

old = 'print(f"  Top narratives: {[(n,v) for n,v in top_narratives]}")'
new = (
    '# Fallback ke keyword scores jika LLM voting kosong\n'
    '    if not top_narratives:\n'
    '        top_narratives = [(n,v) for n,v in top_keyword if v > 0][:3]\n'
    '        print(f"  Top narratives (keyword fallback): {top_narratives}")\n'
    '    else:\n'
    '        print(f"  Top narratives: {[(n,v) for n,v in top_narratives]}")'
)
c = c.replace(old, new, 1)
with open("core/narrative_scanner.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
