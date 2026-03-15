import asyncio, sys, re, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from core.llm_clients import call_llm

async def test():
    prompt = 'Pilih TOP 3 narasi dari: CRYPTO_BULL, INFLATION_HEDGE, RISK_OFF, AI_TECH. Balas JSON: {"narratives":["N1","N2","N3"],"risk_profile":"moderate","reasoning":"singkat","rotation_urgency":"low"}'
    ok, resp = await call_llm("qwen", "Analis macro. Balas JSON saja.", prompt)
    print(f"ok: {ok}")
    print(f"raw: {resp[:200] if resp else 'EMPTY'}")
    if resp:
        resp_clean = re.sub(r'^`json\s*|`\s*$', '', resp.strip())
        m = re.search(r'\{.*\}', resp_clean, re.DOTALL)
        print(f"json found: {bool(m)}")
        if m:
            try:
                r = json.loads(m.group())
                print(f"narratives: {r.get('narratives')}")
            except Exception as e:
                print(f"parse error: {e}")

asyncio.run(test())
