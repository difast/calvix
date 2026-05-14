from aiogram import Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage

from bot.middlewares.business_middleware import BusinessMiddleware
from bot.services.business_loader import BusinessLoader


def create_dispatcher_for_bot(business_id: int, business_loader: BusinessLoader) -> Dispatcher:
    """Создание диспетчера для конкретного бота"""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем middleware с бизнес-контекстом
    dp.message.middleware(BusinessMiddleware(business_loader))
    dp.callback_query.middleware(BusinessMiddleware(business_loader))

    # Импортируем фабрики роутеров — каждый вызов создаёт НОВЫЙ роутер
    from bot.handlers.start import create_start_router
    from bot.handlers.message import create_message_router
    from bot.handlers.callback import create_callback_router
    from bot.handlers.admin import create_admin_router

    dp.include_router(create_start_router())
    dp.include_router(create_message_router())
    dp.include_router(create_callback_router())
    dp.include_router(create_admin_router())

    return dp