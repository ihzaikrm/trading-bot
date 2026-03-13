c = open('backtest/engine.py', encoding='utf-8').read()
lines = c.split('\n')
lines[34] = '    if score >= 4:'
c = '\n'.join(lines)
open('backtest/engine.py', 'w', encoding='utf-8').write(c)
print('Fixed engine.py line 34')

# Verify kedua file
for f in ['core/signal_engine.py', 'backtest/engine.py']:
    c = open(f, encoding='utf-8').read()
    hits = [l.strip() for l in c.split('\n') if 'vol_ratio >' in l or 'score >= ' in l]
    print(f'\n{f}:')
    for h in hits: print(' ', h)
