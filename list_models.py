import httpx, os, json
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('QWEN_API_KEY')

r = httpx.get('https://openrouter.ai/api/v1/models',
    headers={'Authorization': f'Bearer {key}'},
    timeout=20)
models = r.json().get('data', [])
free = [m['id'] for m in models if ':free' in m['id']]
print(f'Total free models: {len(free)}')
for m in free[:20]:
    print(' -', m)
