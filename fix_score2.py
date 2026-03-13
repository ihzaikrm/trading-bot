c = open('core/signal_engine.py', encoding='utf-8').read()
lines = c.split('\n')
# Hanya fix line 33 (BTC Vol-TSMOM) — bukan line 80
lines[33] = '    if score >= 4:'
c = '\n'.join(lines)
open('core/signal_engine.py', 'w', encoding='utf-8').write(c)
print('Fixed line 33')

# Cek backtest/engine.py juga
c2 = open('backtest/engine.py', encoding='utf-8').read()
lines2 = c2.split('\n')
for i,l in enumerate(lines2):
    if 'score >= 5' in l:
        print(f'engine.py LINE {i}: {repr(l)}')
        print(f'  PREV: {repr(lines2[i-1])}')
        print(f'  NEXT: {repr(lines2[i+1])}')
