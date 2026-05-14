from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from bot.repositories.base_repo import BaseRepository
from bot.models import Lead


class LeadRepository(BaseRepository):
    
    async def get_or_create(self, business_id: int, telegram_id: int, username: str = None, full_name: str = None) -> int:
        """Получить или создать лида"""
        session = await self._get_session()
        try:
            # Ищем существующего
            result = await session.execute(
                select(Lead).where(
                    Lead.business_id == business_id,
                    Lead.telegram_id == telegram_id
                )
            )
            lead = result.scalar_one_or_none()
            
            if lead:
                # Обновляем last_active
                lead.last_active = datetime.now()
                if username:
                    lead.username = username
                if full_name:
                    lead.full_name = full_name
                await session.commit()
                return lead.id
            else:
                # Создаём нового
                lead = Lead(
                    business_id=business_id,
                    telegram_id=telegram_id,
                    username=username,
                    full_name=full_name,
                    status="COLD"
                )
                session.add(lead)
                await session.commit()
                await session.refresh(lead)
                return lead.id
        finally:
            await self._close_session(session)
    
    async def update_status(self, lead_id: int, status: str):
        session = await self._get_session()
        try:
            await session.execute(
                update(Lead)
                .where(Lead.id == lead_id)
                .values(status=status, last_active=datetime.now())
            )
            await session.commit()
        finally:
            await self._close_session(session)
    
    async def update_phone(self, lead_id: int, phone: str):
        session = await self._get_session()
        try:
            await session.execute(
                update(Lead)
                .where(Lead.id == lead_id)
                .values(phone=phone)
            )
            await session.commit()
        finally:
            await self._close_session(session)
    
    async def get(self, lead_id: int) -> Lead | None:
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Lead).where(Lead.id == lead_id)
            )
            return result.scalar_one_or_none()
        finally:
            await self._close_session(session)
    
    async def get_by_telegram_id(self, business_id: int, telegram_id: int) -> Lead | None:
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Lead).where(
                    Lead.business_id == business_id,
                    Lead.telegram_id == telegram_id
                )
            )
            return result.scalar_one_or_none()
        finally:
            await self._close_session(session)
    
    async def get_hot_by_business(self, business_id: int) -> list[Lead]:
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Lead).where(
                    Lead.business_id == business_id,
                    Lead.status == "HOT"
                )
            )
            return result.scalars().all()
        finally:
            await self._close_session(session)