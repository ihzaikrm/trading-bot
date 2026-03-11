import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('GEMINI_API_KEY')
print(f"Key: {key[:15]}...")
r = httpx.post(
    'https://api.groq.com/openai/v1/chat/completions',
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    json={'model': 'llama-3.3-70b-versatile', 'messages': [{'role':'user','content':'Reply: OK'}], 'max_tokens': 10},
    timeout=15
)
print(f"Status: {r.status_code}")
print(r.text[:200])
