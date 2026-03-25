import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('OPENROUTER_API_KEY')
if not API_KEY:
    raise ValueError("API key not found")

async def test_openrouter():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen/qwen-turbo",
        "messages": [{"role": "user", "content": "Say hello"}],
        "max_tokens": 10
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers) as resp:
            data = await resp.json()
            print("Response:", data)

asyncio.run(test_openrouter())
