import requests, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('QWEN_API_KEY','')
print('Key:', key[:15])
r = requests.post('https://openrouter.ai/api/v1/chat/completions',
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    json={'model': 'qwen/qwen-turbo', 'messages': [{'role':'user','content':'balas: ok'}], 'max_tokens': 10},
    timeout=15)
print('Status:', r.status_code)
print('Response:', r.text[:200])
