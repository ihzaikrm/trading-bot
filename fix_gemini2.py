import os, re
with open('config/settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''"gemini": LLMConfig(
        name="Gemini 2.5 Flash (OpenRouter)",
        api_key=OR,
        model="google/gemini-2.0-flash-001",
        base_url="https://openrouter.ai/api/v1",'''

new = '''"gemini": LLMConfig(
        name="Gemini 2.0 Flash (Native)",
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model="gemini-2.0-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",'''

content = content.replace(old, new)
with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
