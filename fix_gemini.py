c = open('config/settings.py', encoding='utf-8').read()
c = c.replace('openai/gpt-oss-120b:free', 'google/gemma-3-27b-it:free')
open('config/settings.py', 'w', encoding='utf-8').write(c)
print('Fixed!')
