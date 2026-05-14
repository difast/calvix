import asyncio
from datetime import datetime
from aiogram import Bot
from bot.repositories import LeadRepository, MessageRepository
from bot.config import settings

followup_tasks = {}


async def schedule_followup(lead_id: int, telegram_id: int, bot: Bot, business_id: int, prompt: str, delay_seconds: int = None):
    if delay_seconds is None:
        delay_seconds = settings.followup_delay_seconds
    
    cancel_followup(lead_id)
    
    async def _send():
        await asyncio.sleep(delay_seconds)
        
        lead_repo = LeadRepository()
        msg_repo = MessageRepository()
        
        lead = await lead_repo.get(lead_id)
        if not lead:
            return
        
        last_message = await msg_repo.get_last_user_message(lead_id, business_id)
        if last_message:
            last_time = last_message["created_at"]
            if isinstance(last_time, datetime):
                if (datetime.now() - last_time).total_seconds() < delay_seconds:
                    return
        
        followup_text = (
            "Привет! 👋\n\n"
            "Вижу, вы ещё не ответили. У меня есть ещё 10 минут сегодня, "
            "чтобы обсудить детали.\n\n"
            "Напишите, если всё ещё актуально."
        )
        
        try:
            await bot.send_message(telegram_id, followup_text)
            print(f"📨 Follow-up отправлен lead_id={lead_id}")
        except Exception as e:
            print(f"❌ Ошибка follow-up: {e}")
    
    task = asyncio.create_task(_send())
    followup_tasks[lead_id] = task


def cancel_followup(lead_id: int):
    if lead_id in followup_tasks:
        followup_tasks[lead_id].cancel()
        del followup_tasks[lead_id]