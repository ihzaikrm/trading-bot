c = open('config/settings.py', encoding='utf-8').read()

c = c.replace('google/gemma-2-9b-it:free', 'google/gemini-2.0-flash-exp:free')
c = c.replace('mistralai/mistral-7b-instruct:free:free', 'mistralai/mistral-small-3.1-24b-instruct:free')
c = c.replace('deepseek/deepseek-r1:free', 'deepseek/deepseek-chat-v3-0324:free')

open('config/settings.py', 'w', encoding='utf-8').write(c)
print('Fixed!')
