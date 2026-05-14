import re
from bot.services.ai_client import AIClient


class SalesAgent:
    def __init__(self, ai_client: AIClient):
        self.ai_client = ai_client
    
    async def get_response(self, user_message: str, conversation_history: list, system_prompt: str) -> str:
        """
        Получить ответ от AI с кастомным промптом
        """
        # Ограничиваем историю
        limited_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        
        messages = limited_history + [{"role": "user", "content": user_message}]
        
        response = await self.ai_client.generate_response(messages, system_prompt)
        
        # Очистка от Markdown
        response = re.sub(r'\*\*(.*?)\*\*', r'\1', response)
        response = re.sub(r'\*(.*?)\*', r'\1', response)
        response = response.replace('*', '').replace('_', '')
        
        return response