import asyncio
from orchestrator.graph import run_graph

async def main():
    print("🚀 Synclavix Trading Pipeline Started")
    while True:
        try:
            await run_graph("main")
            await asyncio.sleep(7200)  # 2 jam
        except KeyboardInterrupt:
            print("\n🛑 Synclavix stopped.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
