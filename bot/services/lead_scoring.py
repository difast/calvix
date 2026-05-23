import re
import json
import asyncio
from typing import List, Tuple


class LeadScoringService:
    _cache = None  # {"hot": [...], "warm": [...], "cold": [...]}

    DEFAULT_HOT = [
        "купить", "цена", "оплатить", "договор", "счет", "покупка",
        "хочу заказать", "нужен срочно", "записаться", "хочу записаться",
        "созвон", "встретиться", "позвоните", "демо", "покажите",
        "запишите", "запись", "хочу попробовать", "когда можно начать",
        "как записаться", "хочу начать", "готов начать", "оформить",
    ]
    DEFAULT_WARM = [
        "интересно", "расскажите", "как работает", "пример",
        "сравнение", "стоимость", "есть ли скидка", "возможно ли",
        "автоматизация", "хочу узнать", "подробнее", "а если",
        "сколько стоит", "какая цена", "что входит", "расскажи",
    ]
    DEFAULT_COLD = [
        "не надо", "не интересно", "потом", "не сейчас",
        "не нужно", "отпишитесь", "спам", "отказаться",
    ]

    @classmethod
    def invalidate_cache(cls):
        cls._cache = None

    @classmethod
    async def _load_keywords(cls):
        if cls._cache is not None:
            return cls._cache
        try:
            from bot.models.database import AsyncSessionLocal
            from bot.models.settings import Setting
            from sqlalchemy import select
            async with AsyncSessionLocal() as session:
                result = {}
                for ktype in ["hot", "warm", "cold"]:
                    row = await session.scalar(select(Setting).where(Setting.key == f"keywords_{ktype}"))
                    if row:
                        result[ktype] = [k.strip() for k in row.value.split(",") if k.strip()]
                    else:
                        result[ktype] = getattr(cls, f"DEFAULT_{ktype.upper()}")
            cls._cache = result
            return cls._cache
        except Exception:
            return {"hot": cls.DEFAULT_HOT, "warm": cls.DEFAULT_WARM, "cold": cls.DEFAULT_COLD}

    @property
    def HOT_KEYWORDS(self):
        return (self.__class__._cache or {}).get("hot", self.DEFAULT_HOT)

    def score(self, message_text: str, history: list) -> Tuple[str, int, List[str]]:
        text = message_text.lower()
        cache = self.__class__._cache or {"hot": self.DEFAULT_HOT, "warm": self.DEFAULT_WARM, "cold": self.DEFAULT_COLD}

        for kw in cache.get("cold", self.DEFAULT_COLD):
            if re.search(re.escape(kw), text, re.IGNORECASE):
                return "COLD", -1, [f"cold:{kw}"]

        for kw in cache.get("hot", self.DEFAULT_HOT):
            if re.search(re.escape(kw), text, re.IGNORECASE):
                return "HOT", 3, [f"hot:{kw}"]

        for kw in cache.get("warm", self.DEFAULT_WARM):
            if re.search(re.escape(kw), text, re.IGNORECASE):
                return "WARM", 1, [f"warm:{kw}"]

        return "COLD", 0, []
