from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from bot.services.business_loader import BusinessLoader


class BusinessMiddleware(BaseMiddleware):
    def __init__(self, business_loader: BusinessLoader):
        super().__init__()
        self.loader = business_loader
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        bot = data.get("bot")
        if bot:
            bot_token = bot.token
            result = self.loader.get_business_by_token(bot_token)
            if result:
                business_id, business = result
                data["business_id"] = business_id
                data["business"] = business
                data["business_prompt"] = business.system_prompt
                data["manager_link"] = business.manager_link
        
        return await handler(event, data)