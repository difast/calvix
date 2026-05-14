import json
from datetime import datetime
from sqlalchemy import text
from bot.models.database import AsyncSessionLocal as async_session_maker


class AnalyticsService:

    async def track(
        self,
        event_type: str,
        business_id: int,
        lead_id: int = None,
        metadata: dict = None
    ):
        try:
            async with async_session_maker() as session:
                await session.execute(
                    text("""
                        INSERT INTO analytics_events
                        (business_id, lead_id, event_type, metadata, created_at)
                        VALUES (:business_id, :lead_id, :event_type, :metadata, :created_at)
                    """),
                    {
                        "business_id": business_id,
                        "lead_id": lead_id,
                        "event_type": event_type,
                        "metadata": json.dumps(metadata or {}, ensure_ascii=False),
                        "created_at": datetime.now()
                    }
                )
                await session.commit()
        except Exception as e:
            print(f"Analytics error: {e}")

    async def get_business_stats(self, business_id: int) -> dict:
        async with async_session_maker() as session:
            # Всего лидов
            result = await session.execute(
                text("SELECT COUNT(*) FROM leads WHERE business_id = :bid"),
                {"bid": business_id}
            )
            total_leads = result.scalar()

            # По статусам
            result = await session.execute(
                text("""
                    SELECT status, COUNT(*) as cnt
                    FROM leads
                    WHERE business_id = :bid
                    GROUP BY status
                """),
                {"bid": business_id}
            )
            statuses = {row.status: row.cnt for row in result}

            # Записи на созвон
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM analytics_events
                    WHERE business_id = :bid
                    AND event_type = 'booking_created'
                """),
                {"bid": business_id}
            )
            bookings = result.scalar()

            # Сообщений сегодня
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM analytics_events
                    WHERE business_id = :bid
                    AND event_type = 'message_sent'
                    AND created_at >= CURRENT_DATE
                """),
                {"bid": business_id}
            )
            messages_today = result.scalar()

            hot = statuses.get("HOT", 0)
            warm = statuses.get("WARM", 0)
            cold = statuses.get("COLD", 0)
            hot_rate = round(hot / total_leads * 100, 1) if total_leads > 0 else 0

            return {
                "total_leads": total_leads,
                "hot": hot,
                "warm": warm,
                "cold": cold,
                "hot_rate": hot_rate,
                "bookings": bookings,
                "messages_today": messages_today
            }

    async def get_platform_stats(self) -> dict:
        async with async_session_maker() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM businesses WHERE is_active = true")
            )
            active_bots = result.scalar()

            result = await session.execute(
                text("SELECT COUNT(*) FROM leads")
            )
            total_leads = result.scalar()

            result = await session.execute(
                text("SELECT COUNT(*) FROM leads WHERE status = 'HOT'")
            )
            total_hot = result.scalar()

            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM analytics_events
                    WHERE event_type = 'booking_created'
                """)
            )
            total_bookings = result.scalar()

            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM analytics_events
                    WHERE event_type = 'message_sent'
                    AND created_at >= CURRENT_DATE
                """)
            )
            messages_today = result.scalar()

            hot_rate = round(total_hot / total_leads * 100, 1) if total_leads > 0 else 0

            return {
                "active_bots": active_bots,
                "total_leads": total_leads,
                "total_hot": total_hot,
                "hot_rate": hot_rate,
                "total_bookings": total_bookings,
                "messages_today": messages_today
            }


analytics = AnalyticsService()