import asyncio
from core.llm_clients import call_llm

async def test():
    result = await call_llm("qwen", "Kamu adalah analis narasi market.",
        "Pilih TOP 3 narasi dari: INFLATION_HEDGE, RISK_OFF, CRYPTO_BULL. Balas HANYA JSON: {\"narratives\":[\"N1\",\"N2\",\"N3\"],\"risk_profile\":\"moderate\",\"urgency\":\"low\"}")
    print("Result:", repr(result[:300]))

asyncio.run(test())
