import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter, Command
from bot.fsm.booking import BookingStates
from bot.services.ai_client import AIClient
from bot.services.sales_agent import SalesAgent
from bot.services.analytics import analytics
from bot.services.supabase_sync import supabase_sync
from bot.repositories import LeadRepository, MessageRepository
from bot.config import settings

logger = logging.getLogger(__name__)

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
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or ""
        user_text = message.text

        business_id = kwargs.get("business_id", 1)
        prompt = kwargs.get("business_prompt", "Ты ассистент по продажам. Отвечай по-русски.")
        business = kwargs.get("business")
        business_name = business.name if business else str(business_id)

        # Лид и история
        lead_id = None
        history = []
        try:
            lead_id = await lead_repo.get_or_create(business_id, user_id, username, full_name)
            history = await msg_repo.get_conversation_history(lead_id, business_id)
        except Exception as e:
            logger.error(f"Ошибка БД (lead/history): {e}")

        # AI ответ
        ai_response = await sales_agent.get_response(user_text, history, prompt)

        # Сохраняем историю
        if lead_id:
            try:
                await msg_repo.save_message(lead_id, business_id, "user", user_text)
                await msg_repo.save_message(lead_id, business_id, "assistant", ai_response)
            except Exception as e:
                logger.error(f"Ошибка сохранения сообщений: {e}")

        # FSM для записи на созвон
        await state.update_data(lead_id=lead_id, business_id=business_id)

        # Трекинг
        try:
            await analytics.track("message_sent", business_id, lead_id, {"text": user_text[:100]})
        except Exception:
            pass

        # Квалификация
        qualification = get_qualification(user_text)
        logger.info(f"Сообщение от {user_id} в бизнес {business_id}: квалификация={qualification!r}, текст={user_text!r}")

        if qualification == "HOT":
            try:
                # Обновляем статус
                if lead_id:
                    await lead_repo.update_status(lead_id, "HOT")

                try:
                    await analytics.track("qualification_changed", business_id, lead_id, {
                        "status": "HOT", "trigger": user_text[:100]
                    })
                except Exception:
                    pass

                # Получаем данные лида
                lead = None
                if lead_id:
                    try:
                        lead = await lead_repo.get(lead_id)
                    except Exception as e:
                        logger.error(f"Ошибка получения лида: {e}")

                client_name = (lead.full_name if lead else None) or full_name or "Неизвестно"
                client_username = (lead.username if lead else None) or username or "нет"
                client_phone = (lead.phone if lead else None) or ""
                trigger_word = next((kw for kw in HOT_KEYWORDS if kw in user_text.lower()), "")

                logger.info(f"HOT ЛИД: бизнес={business_name}, клиент={client_name}, trigger={trigger_word!r}")

                # Уведомление админу
                for admin_id in settings.admin_ids:
                    try:
                        await message.bot.send_message(
                            admin_id,
                            f"🔥 HOT ЛИД!\n"
                            f"Бизнес: {business_name}\n"
                            f"Клиент: {client_name}\n"
                            f"Username: @{client_username}\n"
                            f"Написал: {user_text}"
                        )
                        logger.info(f"HOT уведомление отправлено admin {admin_id}")
                    except Exception as e:
                        logger.error(f"Ошибка HOT уведомления admin {admin_id}: {e}")

                # Supabase
                try:
                    await supabase_sync.push_hot_lead(
                        business_id=business_id,
                        business_name=business_name,
                        telegram_id=user_id,
                        username=username,
                        full_name=full_name,
                        phone=client_phone,
                        last_message=user_text,
                        trigger_word=trigger_word,
                    )
                except Exception as e:
                    logger.error(f"Supabase HOT sync error: {e}")

            except Exception as e:
                logger.error(f"Критическая ошибка HOT блока: {e}", exc_info=True)

            await message.answer(ai_response, reply_markup=get_book_button())

        elif qualification == "WARM":
            try:
                if lead_id:
                    await lead_repo.update_status(lead_id, "WARM")
                await analytics.track("qualification_changed", business_id, lead_id, {"status": "WARM"})
            except Exception as e:
                logger.error(f"Ошибка WARM блока: {e}")

            if len(history) >= 4:
                await message.answer(ai_response, reply_markup=get_book_button())
            else:
                await message.answer(ai_response)

        else:
            await message.answer(ai_response)

    return router
