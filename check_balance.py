import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('QWEN_API_KEY')
r = httpx.get('https://openrouter.ai/api/v1/auth/key', headers={'Authorization': f'Bearer {key}'})
print(r.json())
