import asyncio, sys, re, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from core.llm_clients import call_all_llms

async def test():
    print("Calling LLMs...")
    try:
        results = await asyncio.wait_for(
            call_all_llms("Balas JSON saja.", '{"narratives":["CRYPTO_BULL","AI_TECH","INFLATION_HEDGE"],"risk_profile":"moderate","reasoning":"test","rotation_urgency":"low"}'),
            timeout=30
        )
        print("Results:", len(results))
        for llm, (ok, resp) in results.items():
            print(llm, ok, str(resp)[:60] if resp else "EMPTY")
    except asyncio.TimeoutError:
        print("TIMEOUT!")
    except Exception as e:
        print("ERROR:", e)

asyncio.run(test())
