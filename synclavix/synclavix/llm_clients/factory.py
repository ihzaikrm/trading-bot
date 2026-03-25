import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

class OpenRouterClient:
    def __init__(self, api_key=None, model="qwen/qwen-turbo"):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    async def generate(self, prompt, max_tokens=150):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/chat/completions", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"Error: {resp.status}"

    async def close(self):
        pass

def get_llm_client(provider="openrouter", model="qwen/qwen-turbo", api_key=None):
    if provider == "openrouter":
        return OpenRouterClient(api_key, model)
    else:
        raise ValueError(f"Provider {provider} not supported")
