import asyncio
import logging
from bot.config import settings
from bot.services.multibot_manager import MultiBotManager
from bot.handlers.admin import set_multibot_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 Запуск MultiBot платформы...")
    
    # Создаём менеджера
    manager = MultiBotManager()
    set_multibot_manager(manager)
    
    # Запускаем всех ботов
    await manager.start_all()
    
    logger.info("✅ Все боты запущены. Ожидание сообщений...")
    
    # Держим процесс живым
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Остановка ботов...")
        await manager.stop_all()


if __name__ == "__main__":
    asyncio.run(main())