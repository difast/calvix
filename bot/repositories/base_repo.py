from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.database import AsyncSessionLocal


class BaseRepository:
    """Базовый репозиторий с управлением сессиями"""
    
    def __init__(self, session: AsyncSession = None):
        self._session = session
        self._external_session = session is not None
    
    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return AsyncSessionLocal()
    
    async def _close_session(self, session: AsyncSession):
        if not self._external_session:
            await session.close()