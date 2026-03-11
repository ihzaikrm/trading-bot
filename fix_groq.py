import re
with open('config/settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Cari dan ganti seluruh blok gemini
pattern = r'("gemini":\s*LLMConfig\()([^}]+?\},)'
replacement = '''"gemini": LLMConfig(
        name="Llama 3.3 70B (Groq)",
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        max_tokens=1024, temperature=0.3,
        requests_per_minute=30,
        role="trend_analyst", weight=0.20,
    ),'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Done!')
