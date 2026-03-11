import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('QWEN_API_KEY')

# Test beberapa model free satu per satu
models_to_test = [
    'google/gemma-3-27b-it:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'mistralai/mistral-small-3.1-24b-instruct:free',
    'qwen/qwen3-4b:free',
]

for model in models_to_test:
    try:
        r = httpx.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={'model': model, 'messages': [{'role':'user','content':'Reply: OK'}], 'max_tokens': 5},
            timeout=15
        )
        if r.status_code == 200:
            print(f'OK: {model}')
        else:
            print(f'FAIL {r.status_code}: {model}')
    except Exception as e:
        print(f'ERROR: {model} - {e}')
