from openai import AsyncOpenAI
from bot.config import settings


class AIClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=60.0,
            max_retries=2
        )
        self.model = settings.ai_model
        self.max_tokens = settings.max_tokens
        self.temperature = settings.ai_temperature

    async def generate_response(self, messages: list, system_prompt: str) -> str:
        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ Ошибка AI: {e}")
            return "Извините, технические неполадки. Свяжитесь с менеджером."