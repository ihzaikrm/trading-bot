with open('core/narrative_scanner.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')

# Fix: tambah timeout 25 detik untuk narrative LLM call
old = '    results = await call_all_llms("Analis macro & narrative trading. Balas JSON saja.", prompt)'
new = '    try:\n        results = await asyncio.wait_for(call_all_llms("Analis macro & narrative trading. Balas JSON saja.", prompt), timeout=25)\n    except asyncio.TimeoutError:\n        print("  Narrative LLM timeout - skip")\n        return [], "moderate", "low", {}'

if old in c:
    c = c.replace(old, new)
    print('OK: timeout added')
else:
    print('Pattern not found')
    # Cari pattern
    lines = c.split('\n')
    for i,l in enumerate(lines):
        if 'call_all_llms' in l and 'narrative' in l.lower():
            print(i, repr(l[:80]))

with open('core/narrative_scanner.py', 'w', encoding='utf-8') as f:
    f.write(c)

try:
    compile(c, 'core/narrative_scanner.py', 'exec')
    print('Syntax OK!')
except SyntaxError as e:
    print('Error:', e)
