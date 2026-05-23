import re
import json
from bot.services.ai_client import AIClient


async def _load_templates() -> list:
    try:
        from bot.models.database import AsyncSessionLocal
        from bot.models.settings import Setting
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            row = await session.scalar(select(Setting).where(Setting.key == "templates"))
            if row:
                return json.loads(row.value)
    except Exception:
        pass
    return []


class SalesAgent:
    def __init__(self, ai_client: AIClient):
        self.ai_client = ai_client

    async def get_response(self, user_message: str, conversation_history: list, system_prompt: str) -> str:
        limited_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history

        # Append active templates to system prompt
        try:
            templates = await _load_templates()
            if templates:
                tpl_block = "\n\nШаблоны сообщений (используй их дословно когда уместно):\n"
                tpl_block += "\n".join(f"— {t['name']}: {t['text']}" for t in templates if t.get('text'))
                system_prompt = system_prompt + tpl_block
        except Exception:
            pass

        messages = limited_history + [{"role": "user", "content": user_message}]
        response = await self.ai_client.generate_response(messages, system_prompt)

        response = re.sub(r'\*\*(.*?)\*\*', r'\1', response)
        response = re.sub(r'\*(.*?)\*', r'\1', response)
        response = response.replace('*', '').replace('_', '')

        return response
