with open('config/settings.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Ganti baris 50-58 (index 49-57)
new_block = '''    "gemini": LLMConfig(
        name="Llama 3.3 70B (Groq)",
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        max_tokens=1024, temperature=0.3,
        requests_per_minute=30,
        role="trend_analyst", weight=0.20,
    ),\n'''

lines[49:58] = [new_block]

with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done!')
