import os, re
with open('config/settings.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace(
    'model="google/gemini-flash-1.5"',
    'model="google/gemini-2.5-flash"'
).replace(
    'model="google/gemini-2.5-flash-preview"',
    'model="google/gemini-2.5-flash"'
).replace(
    'model="x-ai/grok-beta"',
    'model="x-ai/grok-3-mini"'
).replace(
    'model="grok-beta"',
    'model="x-ai/grok-3-mini"'
)
with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done! settings.py updated.')
