import asyncio

class DummyLLMClient:
    async def generate(self, prompt):
        # Simulasi respons LLM
        return "BUY"  # contoh sederhana

def get_llm_client(provider, model=None):
    # Untuk sementara, selalu kembalikan DummyLLMClient
    return DummyLLMClient()
