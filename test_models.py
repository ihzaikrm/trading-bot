import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('QWEN_API_KEY')

models = [
    'google/gemini-2.5-pro-exp-03-25:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'mistralai/mistral-7b-instruct:free',
    'deepseek/deepseek-r1:free',
]

for m in models:
    r = httpx.post('https://openrouter.ai/api/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/ihzaikrm/trading-bot',
            'X-Title': 'Trading Bot'
        },
        json={'model': m, 'messages':[{'role':'user','content':'hi'}], 'max_tokens':5},
        timeout=20)
    status = r.status_code
    brief = r.text[:100]
    print(f'{m}: {status} | {brief}')
