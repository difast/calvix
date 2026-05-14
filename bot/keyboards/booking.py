from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def booking_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для предложения записи на созвон
    """
    buttons = [
        [InlineKeyboardButton(text="📅 Записаться на созвон", callback_data="book_call")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_booking_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для подтверждения записи
    """
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, подтверждаю", callback_data="confirm_booking"),
            InlineKeyboardButton(text="❌ Нет, отменить", callback_data="cancel_booking")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)