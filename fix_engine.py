content = open('backtest/engine.py').read()
lines = content.split('\n')
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Cari baris yang salah indentasi
    if line.strip().startswith('BAH_SYMBOLS') and not line.startswith('            '):
        # Ganti 7 baris berikutnya dengan versi yang benar
        new_lines.append('            BAH_SYMBOLS = {"GC=F", "^GSPC"}')
        new_lines.append('            if use_kelly and symbol not in BAH_SYMBOLS:')
        new_lines.append('                DEFAULT_WR = {"BTC/USDT": 0.41}')
        new_lines.append('                prior_wr   = DEFAULT_WR.get(symbol, 0.40)')
        new_lines.append('                prior_n    = 20')
        new_lines.append('                obs_wins   = sum(1 for t in trades if t["pnl"] > 0)')
        new_lines.append('                obs_n      = len(trades)')
        new_lines.append('                blended_wr = (prior_wr * prior_n + obs_wins) / (prior_n + obs_n)')
        new_lines.append('                frac       = _kelly_fraction(blended_wr, tp_pct, sl_pct)')
        # Skip baris lama sampai ketemu 'else' atau 'elif'
        while i < len(lines) and not lines[i].strip().startswith('elif symbol in BAH'):
            i += 1
        new_lines.append('            elif symbol in BAH_SYMBOLS:')
        new_lines.append('                frac = 0.90')
        i += 2  # skip 'elif' dan 'frac = 0.90' lama
    else:
        new_lines.append(line)
        i += 1
open('backtest/engine.py', 'w').write('\n'.join(new_lines))
print('Done!')
# Verify
c = open('backtest/engine.py').read()
try:
    compile(c, 'engine.py', 'exec')
    print('Syntax OK!')
except SyntaxError as e:
    print(f'Syntax Error: {e}')
