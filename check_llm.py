with open('core/llm_clients.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')
lines = c.split('\n')
idx = next(i for i,l in enumerate(lines) if 'def call_all_llms' in l)
print('\n'.join([str(i)+': '+lines[i] for i in range(idx, min(idx+20, len(lines)))]))
