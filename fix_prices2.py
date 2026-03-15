c = open('bot.py', encoding='utf-8').read()

old = '        price, change, rsi, macd_hist, macd_cross = result\n        print(f"  {name}:  | RSI:{rsi} | MACD:{macd_cross}")'

new = '        price, change, rsi, macd_hist, macd_cross = result\n        current_prices[name] = price\n        print(f"  {name}:  | RSI:{rsi} | MACD:{macd_cross}")'

if old in c:
    c = c.replace(old, new)
    open('bot.py', 'w', encoding='utf-8').write(c)
    print('OK: current_prices diisi per aset')
else:
    print('SKIP')
