from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


def create_start_router() -> Router:
    router = Router()

    @router.message(Command("start"))
    async def cmd_start(message: Message, **kwargs):
        business = kwargs.get("business")
        
        if business and business.welcome_message:
            welcome_text = business.welcome_message
        else:
            welcome_text = "👋 Добро пожаловать! Чем могу помочь?"
        
        await message.answer(welcome_text)

    return router