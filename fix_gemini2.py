c = open('config/settings.py', encoding='utf-8').read()
c = c.replace('google/gemma-3-27b-it:free', 'z-ai/glm-4.5-air:free')
open('config/settings.py', 'w', encoding='utf-8').write(c)
print('Fixed!')
