with open('config/settings.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('model="google/gemini-2.5-flash"', 'model="google/gemini-2.0-flash-001"')
with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
