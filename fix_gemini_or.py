import os, re
with open('config/settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Ganti semua konfigurasi gemini ke OpenRouter
old_block = content[content.find('"gemini": LLMConfig('):content.find('"gemini": LLMConfig(')+400]
new_block = '''    "gemini": LLMConfig(
        name="Gemini 2.5 Flash Lite (OpenRouter)",
        api_key=OR,
        model="google/gemini-2.5-flash-lite",
        base_url="https://openrouter.ai/api/v1",
        max_tokens=1024, temperature=0.3,
        requests_per_minute=10,
        role="trend_analyst", weight=0.20,
    ),'''

# Cari dan replace blok gemini
import re
pattern = r'"gemini": LLMConfig\([^)]+\),'
new_content = re.sub(pattern, new_block, content, flags=re.DOTALL)
with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Done!')
