from bot.repositories import BusinessRepository
from bot.models import Business


class BusinessLoader:
    """Загрузчик бизнесов из БД"""
    
    def __init__(self):
        self.business_repo = BusinessRepository()
        self._cache: dict[int, Business] = {}
        self._token_to_id: dict[str, int] = {}
    
    async def load_all_active(self) -> list[Business]:
        """Загрузить все активные бизнесы из БД"""
        businesses = await self.business_repo.get_all_active()
        self._cache = {b.id: b for b in businesses}
        self._token_to_id = {b.bot_token: b.id for b in businesses}
        return businesses
    
    async def reload(self):
        """Перезагрузить бизнесы (для команды /reload)"""
        return await self.load_all_active()
    
    def get_business(self, business_id: int) -> Business | None:
        """Получить бизнес по ID из кэша"""
        return self._cache.get(business_id)
    
    def get_business_by_token(self, token: str) -> tuple[int, Business] | None:
        """Получить ID и бизнес по токену"""
        business_id = self._token_to_id.get(token)
        if business_id:
            return business_id, self._cache.get(business_id)
        return None
    
    def get_prompt(self, business_id: int) -> str:
        """Получить промпт бизнеса"""
        business = self._cache.get(business_id)
        return business.system_prompt if business else None
    
    def get_manager_link(self, business_id: int) -> str:
        """Получить ссылку на менеджера"""
        business = self._cache.get(business_id)
        return business.manager_link if business else "@akovpyat"