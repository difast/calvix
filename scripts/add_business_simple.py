#!/usr/bin/env python3
"""
Простой скрипт для добавления бизнеса (работает без переключения .env)
Запуск: python scripts/add_business_simple.py
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from bot.models import Business, Base

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/salesbot"


async def add_business():
    print("\n🆕 ДОБАВЛЕНИЕ НОВОГО БИЗНЕСА\n")
    
    bot_token = input("🔑 Токен Telegram бота: ").strip()
    name = input("📝 Название бизнеса: ").strip()
    manager_link = input("👤 Ссылка на менеджера (например @username): ").strip() or "@akovpyat"
    
    print("\n💬 Введите промпт для AI (на русском):")
    print("Пример: Ты продаёшь стройматериалы. Твоя задача...")
    system_prompt = input("Промпт: ").strip()
    
    if not all([bot_token, name, system_prompt]):
        print("❌ Ошибка: токен, название и промпт обязательны")
        return
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
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
        print(f"\n✅ Бизнес добавлен! ID: {business.id}")
        print(f"📌 Теперь выполните команду /reload в админ-боте")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(add_business())