c = open('config/settings.py', encoding='utf-8').read()

c = c.replace('google/gemini-2.5-pro-exp-03-25:free', 'openai/gpt-oss-120b:free')
c = c.replace('meta-llama/llama-3.3-70b-instruct:free', 'qwen/qwen3-next-80b-a3b-instruct:free')
c = c.replace('mistralai/mistral-7b-instruct:free', 'mistralai/mistral-small-3.1-24b-instruct:free')
c = c.replace('deepseek/deepseek-r1:free', 'nvidia/nemotron-3-super-120b-a12b:free')

open('config/settings.py', 'w', encoding='utf-8').write(c)
print('Fixed!')
