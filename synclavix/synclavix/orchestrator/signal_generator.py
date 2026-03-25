import asyncio
import os
from dotenv import load_dotenv
from llm_clients.factory import get_llm_client

load_dotenv()

async def generate_signal(asset, price, news_summary=None):
    """
    Memanggil LLM untuk mendapatkan sinyal BUY/SELL/HOLD.
    """
    system = """Anda adalah analis trading profesional. Berdasarkan data teknikal dan makro yang diberikan, 
    putuskan apakah Anda akan BUY, SELL, atau HOLD. 
    Berikan alasan singkat lalu sinyal dalam format JSON:
    {"reason": "...", "signal": "BUY/SELL/HOLD"}"""

    prompt = f"""
    Aset: {asset}
    Harga saat ini: ${price}
    {f"Berita: {news_summary}" if news_summary else "Tidak ada berita"}
    """
    try:
        client = get_llm_client("openrouter", model="qwen/qwen-turbo")
        # Gunakan system message jika didukung; jika tidak, satukan dalam prompt
        # Kita satukan dalam satu prompt karena client kita hanya support user message.
        full_prompt = system + "\n\n" + prompt
        response = await client.generate(full_prompt, max_tokens=100)
        await client.close()
        print(f"Raw LLM response: {response}")
        # Cari JSON dalam response
        import json
        import re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group())
            signal = data.get("signal", "HOLD").upper()
            if signal in ["BUY", "SELL", "HOLD"]:
                return signal, 0.7 if signal != "HOLD" else 0.5
        # fallback
        return "HOLD", 0.5
    except Exception as e:
        print(f"LLM error: {e}")
        return "HOLD", 0.5
