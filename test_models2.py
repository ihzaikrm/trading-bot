import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('QWEN_API_KEY')

# Model free yang kemungkinan aktif di OpenRouter
models = [
    'google/gemini-2.0-flash-exp:free',
    'google/gemma-3-27b-it:free',
    'deepseek/deepseek-chat:free',
    'deepseek/deepseek-prover-v2:free',
    'meta-llama/llama-4-scout:free',
    'microsoft/mai-ds-r1:free',
    'nousresearch/deephermes-3-llama-3-8b-preview:free',
]

for m in models:
    r = httpx.post('https://openrouter.ai/api/v1/chat/completions',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
                 'HTTP-Referer': 'https://github.com/ihzaikrm/trading-bot'},
        json={'model': m, 'messages':[{'role':'user','content':'hi'}], 'max_tokens':5},
        timeout=20)
    ok = 'choices' in r.text
    print(f'{"OK" if ok else r.status_code} | {m}')
