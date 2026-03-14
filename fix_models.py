c = open('config/settings.py', encoding='utf-8').read()

fixes = {
    'google/gemini-flash-1.5-8b': 'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.1-8b-instruct': 'meta-llama/llama-3.3-70b-instruct:free',
    'openai/gpt-4o-mini': 'meta-llama/llama-3.3-70b-instruct:free',
    'x-ai/grok-3-mini': 'x-ai/grok-2-1212',
    'x-ai/grok-beta': 'x-ai/grok-2-1212',
    'deepseek/deepseek-chat': 'deepseek/deepseek-r1:free',
    'mistralai/mistral-7b-instruct': 'mistralai/mistral-7b-instruct:free',
}

for old, new in fixes.items():
    if old in c:
        c = c.replace(old, new)
        print(f'Fixed: {old} -> {new}')

open('config/settings.py', 'w', encoding='utf-8').write(c)
print('Done!')
