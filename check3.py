c = open('config/settings.py', encoding='utf-8').read()

# Cek model aktual
for llm in ['gemini','gpt','grok','deepseek']:
    idx = c.find('"'+llm+'"')
    block = c[idx:idx+200]
    import re
    model = re.search(r'model="([^"]+)"', block)
    name = re.search(r'name="([^"]+)"', block)
    apikey = re.search(r'api_key=(\w+)', block)
    print(f'{llm}: model={model.group(1) if model else "?"} | api_key_var={apikey.group(1) if apikey else "?"}')

# Cek variable OPENROUTER_API_KEY
if 'OPENROUTER_API_KEY' in c:
    idx = c.find('OPENROUTER_API_KEY')
    print('\nOPENROUTER_API_KEY def:', c[idx:idx+80])
if 'QWEN_API_KEY' in c:
    idx = c.find('QWEN_API_KEY')
    print('QWEN_API_KEY ref:', c[idx:idx+80])
