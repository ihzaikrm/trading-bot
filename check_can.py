with open('core/llm_clients.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')
lines = c.split('\n')
# Cek RateLimiter.can()
idx = next(i for i,l in enumerate(lines) if 'def can(' in l or 'def can(' in l)
print('\n'.join([str(i)+': '+lines[i] for i in range(max(0,idx-10), min(idx+15, len(lines)))]))
