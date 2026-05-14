from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.config import settings
from bot.services.analytics import analytics

multibot_manager = None


def set_multibot_manager(manager):
    global multibot_manager
    multibot_manager = manager


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def create_admin_router() -> Router:
    router = Router()

    @router.message(Command("stats"))
    async def cmd_stats(message: Message, business_id: int = None, **kwargs):
        if not is_admin(message.from_user.id):
            await message.answer("❌ Нет доступа")
            return
        try:
            stats = await analytics.get_platform_stats()
            await message.answer(
                f"📊 ПЛАТФОРМА — ОБЩАЯ СТАТИСТИКА\n\n"
                f"🤖 Активных ботов: {stats['active_bots']}\n"
                f"👥 Всего лидов: {stats['total_leads']}\n"
                f"🔥 HOT лидов: {stats['total_hot']} ({stats['hot_rate']}%)\n"
                f"📅 Записей на созвон: {stats['total_bookings']}\n"
                f"💬 Сообщений сегодня: {stats['messages_today']}"
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    @router.message(Command("mystats"))
    async def cmd_mystats(message: Message, business_id: int = None, **kwargs):
        if not business_id:
            await message.answer("❌ Бизнес не определён")
            return
        try:
            stats = await analytics.get_business_stats(business_id)
            await message.answer(
                f"📊 СТАТИСТИКА ВАШЕГО БОТА\n\n"
                f"👥 Всего лидов: {stats['total_leads']}\n"
                f"🔥 HOT: {stats['hot']}\n"
                f"🟡 WARM: {stats['warm']}\n"
                f"🔵 COLD: {stats['cold']}\n"
                f"📈 Конверсия в HOT: {stats['hot_rate']}%\n"
                f"📅 Записей на созвон: {stats['bookings']}\n"
                f"💬 Сообщений сегодня: {stats['messages_today']}"
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    @router.message(Command("hot"))
    async def cmd_hot_leads(message: Message, business_id: int = None, **kwargs):
        if not is_admin(message.from_user.id):
            await message.answer("❌ Нет доступа")
            return
        await message.answer("🔥 Список HOT лидов — используй DataLens дашборд")

    @router.message(Command("reload"))
    async def cmd_reload(message: Message, business_id: int = None, **kwargs):
        if not is_admin(message.from_user.id):
            await message.answer("❌ Нет доступа")
            return
        if not multibot_manager:
            await message.answer("❌ Менеджер ботов не инициализирован")
            return
        await message.answer("🔄 Перезагрузка...")
        try:
            await multibot_manager.reload()
            await message.answer("✅ Готово. Боты обновлены.")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    return router