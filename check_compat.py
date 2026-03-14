with open('core/llm_clients.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')
lines = c.split('\n')

# Cari _openai_compat
idx = next(i for i,l in enumerate(lines) if 'async def _openai_compat' in l)
print('\n'.join([str(i)+': '+lines[i] for i in range(idx, min(idx+20, len(lines)))]))
