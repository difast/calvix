import asyncio
import aiohttp

async def test_telegram():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.telegram.org", timeout=10) as resp:
                text = await resp.text()
                print(f"✅ Telegram API доступен: {text[:100]}")
                return True
    except Exception as e:
        print(f"❌ Telegram API недоступен: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_telegram())