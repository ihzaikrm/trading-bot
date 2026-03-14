with open('core/llm_clients.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')
lines = c.split('\n')
idx = next(i for i,l in enumerate(lines) if '_rl' in l and 'class' not in l and 'def' not in l)
print('\n'.join([str(i)+': '+lines[i] for i in range(max(0,idx-5), min(idx+20, len(lines)))]))
