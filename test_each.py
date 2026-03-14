import asyncio, sys, httpx
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from config.settings import LLM_CONFIGS
import os

key = os.getenv('QWEN_API_KEY','')

async def test_one(name, cfg):
    try:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": cfg.model, "messages": [{"role":"user","content":"balas: ok"}], "max_tokens": 10}
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{cfg.base_url}/chat/completions", headers=headers, json=payload)
            print(f"{name}: {r.status_code} | {cfg.model}")
    except Exception as e:
        print(f"{name}: ERROR - {e}")

async def main():
    tasks = [test_one(n, c) for n, c in LLM_CONFIGS.items()]
    await asyncio.gather(*tasks)

asyncio.run(main())
