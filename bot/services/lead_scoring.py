import re
from typing import List, Tuple


class LeadScoringService:
    HOT_KEYWORDS = [
        "купить", "цена", "оплатить", "договор", "счет", "покупка",
        "хочу заказать", "нужен срочно", "записаться", "хочу записаться",
        "созвон", "встретиться", "позвоните", "демо", "покажите",
        "запишите", "запись", "хочу попробовать", "когда можно начать",
        "как записаться", "хочу начать", "готов начать", "оформить",
    ]

    WARM_KEYWORDS = [
        "интересно", "расскажите", "как работает", "пример",
        "сравнение", "стоимость", "есть ли скидка", "возможно ли",
        "автоматизация", "хочу узнать", "подробнее", "а если",
        "сколько стоит", "какая цена", "что входит", "расскажи",
    ]

    COLD_KEYWORDS = [
        "не надо", "не интересно", "потом", "не сейчас",
        "не нужно", "отпишитесь", "спам", "отказаться",
    ]

    def score(self, message_text: str, history: List[dict]) -> Tuple[str, int, List[str]]:
        text = message_text.lower()

        # COLD — отрицательный сигнал, проверяем первым
        for kw in self.COLD_KEYWORDS:
            if re.search(re.escape(kw), text, re.IGNORECASE):
                return "COLD", -1, [f"cold:{kw}"]

        # HOT — любое совпадение сразу HOT
        for kw in self.HOT_KEYWORDS:
            if re.search(re.escape(kw), text, re.IGNORECASE):
                return "HOT", 3, [f"hot:{kw}"]

        # WARM — любое совпадение сразу WARM
        for kw in self.WARM_KEYWORDS:
            if re.search(re.escape(kw), text, re.IGNORECASE):
                return "WARM", 1, [f"warm:{kw}"]

        return "COLD", 0, []
