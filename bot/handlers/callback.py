from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.fsm.booking import BookingStates
from bot.services.booking import create_booking, validate_phone, validate_datetime
from bot.services.analytics import analytics
from bot.services.supabase_sync import supabase_sync
from bot.repositories import LeadRepository
from bot.config import settings


def create_callback_router() -> Router:
    router = Router()
    lead_repo = LeadRepository()

    @router.callback_query(F.data == "book_call")
    async def book_call_start(callback: CallbackQuery, state: FSMContext, **kwargs):
        await callback.message.answer(
            "📅 На какое число и время вам удобно?\n\n"
            "Примеры: завтра в 15:00, сегодня в 18:30, 15.01 в 14:00"
        )
        await state.set_state(BookingStates.waiting_for_datetime)
        await callback.answer()

    @router.message(BookingStates.waiting_for_datetime)
    async def process_datetime(message: CallbackQuery, state: FSMContext, **kwargs):
        valid, formatted, dt = validate_datetime(message.text)
        if not valid:
            await message.answer(
                "❌ Не понял дату. Попробуй так:\n"
                "• завтра в 15:00\n• сегодня в 18:30\n• 20.06 в 14:00"
            )
            return

        await state.update_data(scheduled_datetime=formatted)
        await state.set_state(BookingStates.waiting_for_phone)
        await message.answer(
            f"✅ Записал: {formatted}\n\n"
            "📞 Теперь напишите ваш номер телефона:"
        )

    @router.message(BookingStates.waiting_for_phone)
    async def process_phone(message: CallbackQuery, state: FSMContext, **kwargs):
        valid, phone = validate_phone(message.text)
        if not valid:
            await message.answer(
                "❌ Не понял номер. Напишите в формате:\n"
                "• +7 912 345 67 89\n• 89123456789"
            )
            return

        state_data = await state.get_data()
        scheduled_datetime = state_data.get("scheduled_datetime")

        await state.update_data(phone=phone)
        await state.set_state(BookingStates.waiting_for_confirmation)

        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking")
            ]
        ])

        await message.answer(
            f"Проверьте данные:\n\n"
            f"📅 Время: {scheduled_datetime}\n"
            f"📞 Телефон: {phone}\n\n"
            f"Всё верно?",
            reply_markup=confirm_keyboard
        )

    @router.callback_query(F.data == "confirm_booking")
    async def confirm_booking(callback: CallbackQuery, state: FSMContext, **kwargs):
        try:
            state_data = await state.get_data()
            phone = state_data.get("phone")
            scheduled_datetime = state_data.get("scheduled_datetime")
            lead_id = state_data.get("lead_id")
            business_id = kwargs.get("business_id", 1)
            business = kwargs.get("business")

            if not phone or not scheduled_datetime:
                await callback.message.answer("❌ Ошибка. Начните запись заново.")
                await state.clear()
                return

            _, message_text = await create_booking(lead_id, phone, scheduled_datetime, None, business_id)
            await callback.message.answer(message_text)
            await state.clear()

            # Данные лида для уведомления
            try:
                lead = await lead_repo.get(lead_id) if lead_id else None
            except Exception:
                lead = None

            # Уведомление админу
            for admin_id in settings.admin_ids:
                try:
                    await callback.message.bot.send_message(
                        admin_id,
                        f"📅 НОВАЯ ЗАПИСЬ НА СОЗВОН!\n"
                        f"Бизнес: {business.name if business else business_id}\n"
                        f"Клиент: {lead.full_name if lead else callback.from_user.full_name}\n"
                        f"Username: @{lead.username if lead else callback.from_user.username or 'нет'}\n"
                        f"📞 Телефон: {phone}\n"
                        f"🕐 Время: {scheduled_datetime}"
                    )
                except Exception as e:
                    print(f"Ошибка уведомления о записи: {e}")

            # Синхронизация с Supabase
            try:
                await supabase_sync.push_booking(
                    business_id=business_id,
                    business_name=business.name if business else "Неизвестно",
                    telegram_id=lead.telegram_id if lead else callback.from_user.id,
                    username=lead.username if lead else (callback.from_user.username or ""),
                    full_name=lead.full_name if lead else (callback.from_user.full_name or ""),
                    phone=phone,
                    scheduled_datetime=scheduled_datetime
                )
            except Exception as e:
                print(f"Supabase booking sync error: {e}")

            # Трекинг
            await analytics.track("booking_created", business_id, lead_id, {
                "phone": phone,
                "scheduled_datetime": scheduled_datetime
            })

        except Exception as e:
            print(f"❌ Критическая ошибка confirm_booking: {e}")
            try:
                await callback.message.answer("❌ Произошла ошибка. Попробуйте позже.")
                await state.clear()
            except Exception:
                pass
        finally:
            try:
                await callback.answer()
            except Exception:
                pass

    @router.callback_query(F.data == "cancel_booking")
    async def cancel_booking(callback: CallbackQuery, state: FSMContext, **kwargs):
        await state.clear()
        await callback.message.answer("❌ Запись отменена.")
        await callback.answer()

    return router
