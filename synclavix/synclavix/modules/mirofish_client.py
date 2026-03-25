import aiohttp
import asyncio
import json
from typing import Optional

class MiroFishClient:
    def __init__(self, base_url="http://localhost:5001"):
        self.base_url = base_url
        self.session = None

    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def run_simulation(self, document_text: str, timeout: int = 60) -> Optional[dict]:
        """
        Kirim dokumen ke MiroFish untuk simulasi.
        Mengembalikan hasil simulasi dalam bentuk dict.
        """
        session = await self._get_session()
        payload = {"document": document_text}
        try:
            async with session.post(f"{self.base_url}/simulate", json=payload, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    print(f"MiroFish error: {resp.status}")
                    return None
        except asyncio.TimeoutError:
            print("MiroFish simulation timed out")
            return None
        except Exception as e:
            print(f"MiroFish connection error: {e}")
            return None

    async def close(self):
        if self.session:
            await self.session.close()

# Contoh penggunaan
async def test():
    client = MiroFishClient()
    result = await client.run_simulation("Berita terbaru tentang inflasi dan kenaikan suku bunga Fed.")
    print("Simulation result:", result)
    await client.close()

if __name__ == "__main__":
    asyncio.run(test())
