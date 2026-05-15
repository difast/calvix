import httpx
from datetime import datetime
from bot.config import settings
import logging

logger = logging.getLogger(__name__)

SUPABASE_PROJECT = "mvhivbqfgteregyhmlhf"
SUPABASE_API_URL = f"https://{SUPABASE_PROJECT}.supabase.co/rest/v1"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im12aGl2YnFmZ3RlcmVneWhtbGhmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg3ODY4NzUsImV4cCI6MjA5NDM2Mjg3NX0.VOfoL-ZO5sNNu9GAEuGPelMOIEqLRSzgqsuzSkVCt1E"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}


class SupabaseSync:

    async def ensure_tables(self):
        # Таблицы создаются вручную в Supabase Dashboard
        logger.info("Supabase: используем REST API")

    async def push_hot_lead(
        self,
        business_id: int,
        business_name: str,
        telegram_id: int,
        username: str,
        full_name: str,
        phone: str,
        last_message: str,
        trigger_word: str
    ):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{SUPABASE_API_URL}/hot_leads",
                    headers=HEADERS,
                    json={
                        "business_id": business_id,
                        "business_name": business_name,
                        "telegram_id": telegram_id,
                        "username": username or "",
                        "full_name": full_name or "Неизвестно",
                        "phone": phone or "",
                        "last_message": last_message[:500] if last_message else "",
                        "trigger_word": trigger_word,
                        "created_at": datetime.now().isoformat()
                    }
                )
            if resp.status_code in (200, 201):
                logger.info(f"Supabase: HOT лид записан — {full_name}")
            else:
                logger.error(f"Supabase push_hot_lead error: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Supabase push_hot_lead error: {e}")

    async def push_booking(
        self,
        business_id: int,
        business_name: str,
        telegram_id: int,
        username: str,
        full_name: str,
        phone: str,
        scheduled_datetime: str
    ):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{SUPABASE_API_URL}/bookings",
                    headers=HEADERS,
                    json={
                        "business_id": business_id,
                        "business_name": business_name,
                        "telegram_id": telegram_id,
                        "username": username or "",
                        "full_name": full_name or "Неизвестно",
                        "phone": phone or "",
                        "scheduled_datetime": scheduled_datetime,
                        "created_at": datetime.now().isoformat()
                    }
                )
            if resp.status_code in (200, 201):
                logger.info(f"Supabase: Запись на созвон — {full_name} в {scheduled_datetime}")
            else:
                logger.error(f"Supabase push_booking error: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Supabase push_booking error: {e}")

    async def close(self):
        pass


supabase_sync = SupabaseSync()