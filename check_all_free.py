import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('QWEN_API_KEY')
r = httpx.get('https://openrouter.ai/api/v1/models', headers={'Authorization': f'Bearer {key}'})
models = [m['id'] for m in r.json()['data'] if ':free' in m['id'].lower()]
print(f'Total free models: {len(models)}')
for m in sorted(models):
    print(m)
