for fname in ['core/signal_engine.py', 'backtest/engine.py']:
    c = open(fname, encoding='utf-8').read()
    # Hanya ganti BTC signal function (bukan yang lain)
    c = c.replace('if score >= 5:\n                return "BUY"', 'if score >= 4:\n                return "BUY"')
    c = c.replace('if score >= 5:\n            return "BUY"', 'if score >= 4:\n            return "BUY"')
    open(fname, 'w', encoding='utf-8').write(c)
    print('score fixed:', fname)

# Fix walk_forward.py default params
c = open('backtest/walk_forward.py', encoding='utf-8').read()
c = c.replace('"BTC/USDT": {"score_threshold": 5, "vol_ratio_min": 1.2', '"BTC/USDT": {"score_threshold": 4, "vol_ratio_min": 1.0')
open('backtest/walk_forward.py', 'w', encoding='utf-8').write(c)
print('wfo default params fixed')
