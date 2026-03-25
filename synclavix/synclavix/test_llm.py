import asyncio
import os
from dotenv import load_dotenv
from llm_clients.factory import get_llm_client

load_dotenv()

async def test():
    try:
        client = get_llm_client("openrouter", model="qwen/qwen-turbo")
        response = await client.generate("Say hello in one sentence.")
        print("Response:", response)
        await client.close()
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
