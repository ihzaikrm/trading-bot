c = open('config/settings.py', encoding='utf-8').read()

c = c.replace('meta-llama/llama-3.3-70b-instruct:free:free', 'meta-llama/llama-3.3-70b-instruct:free')
c = c.replace('google/gemini-2.0-flash-exp:free', 'google/gemini-2.5-pro-exp-03-25:free')
c = c.replace('deepseek/deepseek-chat-v3-0324:free', 'deepseek/deepseek-r1:free')
c = c.replace('mistralai/mistral-small-3.1-24b-instruct:free', 'mistralai/mistral-7b-instruct:free')

open('config/settings.py', 'w', encoding='utf-8').write(c)
print('Fixed!')
