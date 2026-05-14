from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DbSessionMiddleware(BaseMiddleware):
    """
    Мидлварь для подключения к БД (можно расширить для передачи сессии)
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Здесь можно добавить создание сессии БД
        # Пока просто передаем управление дальше
        result = await handler(event, data)
        return result