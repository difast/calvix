import re
from datetime import datetime
from bot.repositories import lead_repo
from bot.repositories.lead_repo import LeadRepository
from bot.repositories.message_repo import MessageRepository


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Проверяет и нормализует номер телефона
    Возвращает (валидный, нормализованный_номер)
    """
    # Удаляем все нецифровые символы
    digits = re.sub(r'\D', '', phone)
    
    # Проверяем длину
    if len(digits) == 11 and digits.startswith('8'):
        # 89123456789 -> +79123456789
        normalized = '+7' + digits[1:]
        return True, normalized
    elif len(digits) == 11 and digits.startswith('7'):
        # 79123456789 -> +79123456789
        normalized = '+' + digits
        return True, normalized
    elif len(digits) == 12 and digits.startswith('7'):
        # +79123456789 -> +79123456789
        normalized = '+' + digits
        return True, normalized
    elif len(digits) == 10:
        # 9123456789 -> +79123456789
        normalized = '+7' + digits
        return True, normalized
    else:
        return False, phone


def validate_datetime(datetime_str: str) -> tuple[bool, str, datetime]:
    """
    Проверяет и парсит дату и время
    Поддерживает форматы:
    - завтра в 15:00
    - сегодня в 18:30
    - 15.01 в 14:00
    - 20 января в 12:00
    - 2025-01-15 15:00
    """
    datetime_str = datetime_str.lower().strip()
    now = datetime.now()
    
    # Простая проверка на ключевые слова
    if "сегодня" in datetime_str:
        # Ищем время
        time_match = re.search(r'(\d{1,2})[:.](\d{2})', datetime_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if dt < now:
                dt = dt.replace(day=dt.day + 1)
            return True, dt.strftime("%d.%m.%Y %H:%M"), dt
    
    elif "завтра" in datetime_str:
        time_match = re.search(r'(\d{1,2})[:.](\d{2})', datetime_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            dt = now.replace(day=now.day + 1, hour=hour, minute=minute, second=0, microsecond=0)
            return True, dt.strftime("%d.%m.%Y %H:%M"), dt
    
    # Формат: 15.01 в 14:00 или 20 января в 12:00
    date_match = re.search(r'(\d{1,2})[\.\s]+(\d{1,2})?', datetime_str)
    time_match = re.search(r'(\d{1,2})[:.](\d{2})', datetime_str)
    
    if date_match and time_match:
        day = int(date_match.group(1))
        # Месяц опционально
        if date_match.group(2):
            month = int(date_match.group(2))
        else:
            month = now.month
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        
        year = now.year
        if month < now.month:
            year += 1
        
        try:
            dt = datetime(year, month, day, hour, minute)
            if dt < now:
                dt = datetime(year + 1, month, day, hour, minute) if month == 1 else datetime(year, month + 1, day, hour, minute)
            return True, dt.strftime("%d.%m.%Y %H:%M"), dt
        except:
            pass
    
    return False, datetime_str, None


async def create_booking(lead_id: int, phone: str, scheduled_datetime: str, scheduled_dt: datetime):
    from bot.repositories.lead_repo import LeadRepository
    
    lead_repo = LeadRepository()
    lead = await lead_repo.get(lead_id)
    
    if not lead:
        return False, None
    
    await lead_repo.update_phone(lead_id, phone)
    
    message = (
        f"✅ Отлично! Я записал вас на созвон.\n\n"
        f"📅 Дата и время: {scheduled_datetime}\n"
        f"📞 Телефон: {phone}\n\n"
        f"Свяжитесь с менеджером для подтверждения: @akovpyat\n\n"
        f"До встречи! 🚀"
    )
    
    return True, message


def get_phone_request_message() -> str:
    """Сообщение с просьбой ввести телефон"""
    return (
        "📞 Отлично! Для записи на созвон мне нужен ваш номер телефона.\n\n"
        "Пожалуйста, напишите номер в формате:\n"
        "• +7 912 345 67 89\n"
        "• 89123456789\n"
        "• 9123456789\n\n"
        "Я проверю и подтвержу."
    )