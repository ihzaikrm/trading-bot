import sys
sys.path.insert(0, '.')

# Baca bot.py
with open('bot.py', 'rb') as f:
    raw = f.read()
c = raw.decode('utf-8-sig')

# Tambah imports di bagian atas
old_imports = 'from core.news_pipeline import get_multi_timeframe_news'
new_imports = '''from core.news_pipeline import get_multi_timeframe_news
from core.performance_boost import (get_fear_greed, apply_fg_to_signal,
    update_trailing_stop, clear_trailing_stop, is_too_correlated)
from core.cot_weekly import (build_cot_prompt, generate_weekly_report,
    should_send_weekly_report, tg as tg_report)'''

if old_imports in c:
    c = c.replace(old_imports, new_imports)
    print('OK: imports added')
else:
    print('SKIP: imports pattern not found')

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(c)

try:
    compile(c, 'bot.py', 'exec')
    print('Syntax OK!')
except SyntaxError as e:
    print('Error:', e)
