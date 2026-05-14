from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.repositories.base_repo import BaseRepository
from bot.models import Business


class BusinessRepository(BaseRepository):
    
    async def get_all_active(self) -> list[Business]:
        """Получить все активные бизнесы"""
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Business).where(Business.is_active == True)
            )
            return result.scalars().all()
        finally:
            await self._close_session(session)
    
    async def get_by_token(self, bot_token: str) -> Business | None:
        """Получить бизнес по токену бота"""
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Business).where(Business.bot_token == bot_token)
            )
            return result.scalar_one_or_none()
        finally:
            await self._close_session(session)
    
    async def get_by_id(self, business_id: int) -> Business | None:
        """Получить бизнес по ID"""
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Business).where(Business.id == business_id)
            )
            return result.scalar_one_or_none()
        finally:
            await self._close_session(session)
    
    async def add(self, bot_token: str, name: str, system_prompt: str, manager_link: str = "@akovpyat") -> Business:
        """Добавить новый бизнес"""
        session = await self._get_session()
        try:
            business = Business(
                bot_token=bot_token,
                name=name,
                system_prompt=system_prompt,
                manager_link=manager_link,
                is_active=True
            )
            session.add(business)
            await session.commit()
            await session.refresh(business)
            return business
        finally:
            await self._close_session(session)
    
    async def update_prompt(self, business_id: int, new_prompt: str):
        """Обновить промпт бизнеса"""
        session = await self._get_session()
        try:
            await session.execute(
                update(Business)
                .where(Business.id == business_id)
                .values(system_prompt=new_prompt)
            )
            await session.commit()
        finally:
            await self._close_session(session)
    
    async def set_active(self, business_id: int, is_active: bool):
        """Включить/выключить бизнес"""
        session = await self._get_session()
        try:
            await session.execute(
                update(Business)
                .where(Business.id == business_id)
                .values(is_active=is_active)
            )
            await session.commit()
        finally:
            await self._close_session(session)