from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter, Command
from bot.fsm.booking import BookingStates
from bot.services.ai_client import AIClient
from bot.services.sales_agent import SalesAgent
from bot.services.analytics import analytics
from bot.repositories import LeadRepository, MessageRepository
from bot.config import settings

HOT_KEYWORDS = [
    "купить", "записаться", "хочу начать", "сколько стоит",
    "цена", "стоимость", "оплатить", "запишите", "давайте",
    "готов", "когда можно", "как записаться", "хочу", "запиши"
]
WARM_KEYWORDS = [
    "интересно", "расскажите", "подробнее",
    "думаю", "возможно", "наверное"
]


def get_qualification(text: str) -> str | None:
    t = text.lower()
    for kw in HOT_KEYWORDS:
        if kw in t:
            return "HOT"
    for kw in WARM_KEYWORDS:
        if kw in t:
            return "WARM"
    return None


def get_book_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📅 Записаться на созвон",
            callback_data="book_call"
        )]
    ])


def create_message_router() -> Router:
    router = Router()
    ai_client = AIClient()
    sales_agent = SalesAgent(ai_client)
    lead_repo = LeadRepository()
    msg_repo = MessageRepository()

    @router.message(F.text, ~StateFilter(BookingStates), ~F.text.startswith("/"))
    async def handle_message(message: Message, state: FSMContext, **kwargs):
        user_id = message.from_user.id
        username = message.from_user.username
        full_name = message.from_user.full_name
        user_text = message.text

        business_id = kwargs.get("business_id", 1)
        prompt = kwargs.get("business_prompt", "You are a sales assistant. Be concise.")

        # Получаем или создаём лида
        lead_id = await lead_repo.get_or_create(business_id, user_id, username, full_name)

        # Получаем историю
        history = await msg_repo.get_conversation_history(lead_id, business_id)

        # Получаем ответ от AI
        ai_response = await sales_agent.get_response(user_text, history, prompt)

        # Сохраняем сообщения
        await msg_repo.save_message(lead_id, business_id, "user", user_text)
        await msg_repo.save_message(lead_id, business_id, "assistant", ai_response)

        # Трекинг сообщения
        await analytics.track("message_sent", business_id, lead_id, {
            "text": user_text[:100]
        })

        # Сохраняем для FSM записи на созвон
        await state.update_data(lead_id=lead_id, business_id=business_id)

        # Квалификация
        qualification = get_qualification(user_text)

        if qualification == "HOT":
            await lead_repo.update_status(lead_id, "HOT")

            # Трекинг квалификации
            await analytics.track("qualification_changed", business_id, lead_id, {
                "status": "HOT",
                "trigger": user_text[:100]
            })

            lead = await lead_repo.get(lead_id)
            for admin_id in settings.admin_ids:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"🔥 HOT ЛИД!\n"
                        f"Бизнес ID: {business_id}\n"
                        f"Клиент: {lead.full_name or 'Неизвестно'}\n"
                        f"Username: @{lead.username or 'нет'}\n"
                        f"Написал: {user_text}"
                    )
                except Exception as e:
                    print(f"Ошибка уведомления: {e}")
            await message.answer(ai_response, reply_markup=get_book_button())

        elif qualification == "WARM":
            await lead_repo.update_status(lead_id, "WARM")

            # Трекинг квалификации
            await analytics.track("qualification_changed", business_id, lead_id, {
                "status": "WARM"
            })

            if len(history) >= 4:
                await message.answer(ai_response, reply_markup=get_book_button())
            else:
                await message.answer(ai_response)

        else:
            await message.answer(ai_response)

    return router