import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('QWEN_API_KEY')
r = httpx.get('https://openrouter.ai/api/v1/models', headers={'Authorization': f'Bearer {key}'})
models = [m for m in r.json()['data'] if 'gemini' in m['id'].lower()]
for m in models:
    price = m.get('pricing', {}).get('prompt', '?')
    print(f"{m['id']} | prompt_price: {price}")
