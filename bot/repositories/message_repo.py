from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from bot.repositories.base_repo import BaseRepository
from bot.models import Message


class MessageRepository(BaseRepository):
    
    async def save_message(self, lead_id: int, business_id: int, role: str, content: str):
        session = await self._get_session()
        try:
            message = Message(
                lead_id=lead_id,
                business_id=business_id,
                role=role,
                content=content
            )
            session.add(message)
            await session.commit()
        finally:
            await self._close_session(session)
    
    async def get_conversation_history(self, lead_id: int, business_id: int, limit: int = 20) -> list[dict]:
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Message.role, Message.content, Message.created_at)
                .where(
                    Message.lead_id == lead_id,
                    Message.business_id == business_id
                )
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            rows = result.all()
            # Возвращаем в хронологическом порядке
            history = [{"role": row.role, "content": row.content} for row in reversed(rows)]
            return history
        finally:
            await self._close_session(session)
    
    async def get_last_user_message(self, lead_id: int, business_id: int) -> dict | None:
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Message.role, Message.content, Message.created_at)
                .where(
                    Message.lead_id == lead_id,
                    Message.business_id == business_id,
                    Message.role == "user"
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            row = result.first()
            if row:
                return {"role": row.role, "content": row.content, "created_at": row.created_at}
            return None
        finally:
            await self._close_session(session)
    
    async def clear_conversation(self, lead_id: int, business_id: int):
        """Очистить историю диалога (для тестов)"""
        session = await self._get_session()
        try:
            await session.execute(
                delete(Message).where(
                    Message.lead_id == lead_id,
                    Message.business_id == business_id
                )
            )
            await session.commit()
        finally:
            await self._close_session(session)