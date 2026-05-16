import re
from datetime import datetime, timedelta
from bot.repositories.lead_repo import LeadRepository


def validate_phone(phone: str) -> tuple[bool, str]:
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits.startswith('8'):
        return True, '+7' + digits[1:]
    elif len(digits) == 11 and digits.startswith('7'):
        return True, '+' + digits
    elif len(digits) == 12 and digits.startswith('7'):
        return True, '+' + digits
    elif len(digits) == 10:
        return True, '+7' + digits
    return False, phone


def validate_datetime(datetime_str: str) -> tuple[bool, str, datetime]:
    datetime_str = datetime_str.lower().strip()
    now = datetime.now()

    if "сегодня" in datetime_str:
        time_match = re.search(r'(\d{1,2})[:.](\d{2})', datetime_str)
        if time_match:
            hour, minute = int(time_match.group(1)), int(time_match.group(2))
            dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if dt < now:
                dt = dt + timedelta(days=1)
            return True, dt.strftime("%d.%m.%Y %H:%M"), dt

    elif "завтра" in datetime_str:
        time_match = re.search(r'(\d{1,2})[:.](\d{2})', datetime_str)
        if time_match:
            hour, minute = int(time_match.group(1)), int(time_match.group(2))
            dt = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            return True, dt.strftime("%d.%m.%Y %H:%M"), dt

    # Формат: 15.01 в 14:00
    date_match = re.search(r'(\d{1,2})[\.\s]+(\d{1,2})?', datetime_str)
    time_match = re.search(r'(\d{1,2})[:.](\d{2})', datetime_str)

    if date_match and time_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2)) if date_match.group(2) else now.month
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
        year = now.year
        if month < now.month:
            year += 1
        try:
            dt = datetime(year, month, day, hour, minute)
            if dt < now:
                try:
                    dt = datetime(year + 1, month, day, hour, minute)
                except ValueError:
                    pass
            return True, dt.strftime("%d.%m.%Y %H:%M"), dt
        except ValueError:
            pass

    return False, datetime_str, None


async def create_booking(lead_id: int, phone: str, scheduled_datetime: str, scheduled_dt: datetime, business_id: int = 1):
    from bot.models.database import AsyncSessionLocal
    from bot.models.booking import Booking

    lead_repo = LeadRepository()

    if lead_id:
        lead = await lead_repo.get(lead_id)
        if lead:
            await lead_repo.update_phone(lead_id, phone)

    try:
        async with AsyncSessionLocal() as session:
            booking = Booking(
                lead_id=lead_id,
                business_id=business_id,
                phone=phone,
                scheduled_at=scheduled_dt,
                status="pending",
            )
            session.add(booking)
            await session.commit()
    except Exception as e:
        print(f"❌ Ошибка сохранения booking в БД: {e}")

    msg = (
        f"✅ Отлично! Я записал вас на созвон.\n\n"
        f"📅 Дата и время: {scheduled_datetime}\n"
        f"📞 Телефон: {phone}\n\n"
        f"Свяжитесь с менеджером для подтверждения: @akovpyat\n\n"
        f"До встречи! 🚀"
    )
    return True, msg
