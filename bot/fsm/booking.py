from aiogram.fsm.state import StatesGroup, State


class BookingStates(StatesGroup):
    """Состояния для процесса записи на созвон"""
    waiting_for_datetime = State()  # Ожидаем дату и время
    waiting_for_phone = State()     # Ожидаем номер телефона
    waiting_for_confirmation = State()  # Ожидаем подтверждение