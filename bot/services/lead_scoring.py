import re
from typing import List, Tuple


class LeadScoringService:
    # Ключевые слова для разных статусов
    HOT_KEYWORDS = [
        "купить", "цена", "оплатить", "договор", "счет", "покупка",
        "хочу заказать", "нужен срочно", "когда внедрите", "записаться",
        "созвон", "встретиться", "позвоните", "демо", "покажите"
    ]
    
    WARM_KEYWORDS = [
        "интересно", "расскажите", "как работает", "пример",
        "сравнение", "стоимость", "есть ли скидка", "возможно ли",
        "автоматизация", "бот", "ai"
    ]
    
    COLD_KEYWORDS = [
        "не надо", "отказаться", "не интересно", "потом", "не сейчас",
        "не нужно", "отпишитесь", "спам"
    ]
    
    def score(self, message_text: str, history: List[dict]) -> Tuple[str, int, List[str]]:
        """
        Возвращает (статус, счет, список причин)
        """
        score = 0
        reasons = []
        
        # Проверяем HOT ключевые слова
        for kw in self.HOT_KEYWORDS:
            if re.search(kw, message_text, re.IGNORECASE):
                score += 3
                reasons.append(f"hot_keyword:{kw}")
        
        # Проверяем WARM ключевые слова
        for kw in self.WARM_KEYWORDS:
            if re.search(kw, message_text, re.IGNORECASE):
                score += 1
                reasons.append(f"warm_keyword:{kw}")
        
        # Проверяем COLD ключевые слова (отрицательные сигналы)
        for kw in self.COLD_KEYWORDS:
            if re.search(kw, message_text, re.IGNORECASE):
                score -= 3
                reasons.append(f"negative:{kw}")
        
        # Длина сообщения (вовлеченность)
        if len(message_text) > 100:
            score += 1
            reasons.append("long_message")
        
        # Вопросительные знаки (интерес)
        if message_text.count('?') >= 2:
            score += 1
            reasons.append("multiple_questions")
        
        # Определяем статус
        if score >= 5:
            status = "HOT"
        elif score >= 2:
            status = "WARM"
        else:
            status = "COLD"
        
        return status, score, reasons