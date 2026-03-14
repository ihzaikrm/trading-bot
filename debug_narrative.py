import asyncio, sys, re, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from core.llm_clients import call_all_llms

async def test():
    prompt = 'Pilih narasi market dominan dari: AI_TECH, CRYPTO_BULL, INFLATION_HEDGE. Balas HANYA JSON ini persis: {"narratives":["AI_TECH","CRYPTO_BULL","INFLATION_HEDGE"],"risk_profile":"moderate","reasoning":"test ok","rotation_urgency":"low"}'
    results = await call_all_llms("Balas JSON saja tanpa teks lain.", prompt)
    for llm, (ok, resp) in results.items():
        print(f"{llm}: ok={ok}")
        if resp:
            print(f"  resp: {repr(resp[:200])}")

asyncio.run(test())
