import asyncio
import logging
import os
from aiohttp import web
from bot.config import settings
from bot.services.multibot_manager import MultiBotManager
from bot.handlers.admin import set_multibot_manager
from bot.services.supabase_sync import supabase_sync
from bot.api.server import create_app, set_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 Запуск MultiBot платформы...")

    manager = MultiBotManager()

    try:
        await supabase_sync.ensure_tables()
        logger.info("✅ Supabase таблицы готовы")
    except Exception as e:
        logger.warning(f"⚠️ Supabase недоступен: {e}")

    set_multibot_manager(manager)
    set_manager(manager)

    await manager.start_all()
    logger.info("✅ Все боты запущены. Ожидание сообщений...")

    # HTTP API для CRM дашборда
    port = int(os.environ.get("PORT", 8080))
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 CRM API запущен на порту {port}")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Остановка...")
        await manager.stop_all()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
