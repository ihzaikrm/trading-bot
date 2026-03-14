c = open('config/settings.py', encoding='utf-8').read()
for llm in ['gemini','grok','deepseek','gpt']:
    idx = c.find('"'+llm+'"')
    print(llm+':')
    print(c[idx:idx+200])
    print('---')
