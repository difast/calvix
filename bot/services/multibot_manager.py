import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from bot.dispatcher import create_dispatcher_for_bot
from bot.services.business_loader import BusinessLoader
from bot.models import Business

logger = logging.getLogger(__name__)


class MultiBotManager:
    """Управляет несколькими Telegram ботами в одном процессе"""

    def __init__(self):
        self.bots: dict[int, Bot] = {}
        self.dispatchers: dict[int, Dispatcher] = {}
        self.loader = BusinessLoader()
        self._tasks: dict[int, asyncio.Task] = {}

    async def start_all(self):
        """Запуск всех активных ботов"""
        logger.info("🚀 Загрузка бизнесов из БД...")
        businesses = await self.loader.load_all_active()
        logger.info(f"📋 Найдено активных бизнесов: {len(businesses)}")

        for business in businesses:
            logger.info(f"⏳ Запускаю бот: {business.name} (ID: {business.id})")
            await self._start_bot(business)

    async def _start_bot(self, business: Business):
        """Запуск одного бота"""
        try:
            logger.info(f"🔑 Токен бота '{business.name}': {business.bot_token[:10]}...")

            bot = Bot(token=business.bot_token)

            logger.info(f"⚙️ Создаю dispatcher для '{business.name}'...")
            dp = create_dispatcher_for_bot(business.id, self.loader)

            logger.info(f"📝 Устанавливаю команды для '{business.name}'...")
            await bot.set_my_commands([
                BotCommand(command="start", description="Начать диалог"),
                BotCommand(command="help", description="Помощь"),
            ])

            self.bots[business.id] = bot
            self.dispatchers[business.id] = dp

            task = asyncio.create_task(dp.start_polling(bot))
            self._tasks[business.id] = task

            logger.info(f"✅ Бот успешно запущен: '{business.name}' (ID: {business.id})")

        except Exception as e:
            logger.error(
                f"❌ Ошибка запуска бота '{business.name}' (ID: {business.id}): {e}",
                exc_info=True
            )

    async def _stop_bot(self, business_id: int):
        """Остановка одного бота"""
        if business_id in self._tasks:
            self._tasks[business_id].cancel()
            try:
                await self._tasks[business_id]
            except asyncio.CancelledError:
                pass
            del self._tasks[business_id]

        if business_id in self.bots:
            await self.bots[business_id].session.close()
            del self.bots[business_id]

        if business_id in self.dispatchers:
            del self.dispatchers[business_id]

        logger.info(f"🛑 Остановлен бот с business_id: {business_id}")

    async def reload(self):
        """Перезагрузка всех ботов (для команды /reload)"""
        logger.info("🔄 Перезагрузка конфигурации...")

        new_businesses = await self.loader.reload()
        new_ids = {b.id for b in new_businesses}
        old_ids = set(self.bots.keys())

        # Останавливаем удалённые или деактивированные боты
        for business_id in old_ids - new_ids:
            logger.info(f"🛑 Останавливаю бот business_id={business_id}...")
            await self._stop_bot(business_id)

        # Запускаем новые боты
        for business in new_businesses:
            if business.id not in self.bots:
                logger.info(f"🆕 Запускаю новый бот: {business.name}...")
                await self._start_bot(business)

        logger.info(f"✅ Перезагрузка завершена. Активных ботов: {len(self.bots)}")

    async def stop_all(self):
        """Остановка всех ботов"""
        logger.info("🛑 Остановка всех ботов...")
        for business_id in list(self.bots.keys()):
            await self._stop_bot(business_id)
        logger.info("✅ Все боты остановлены.")