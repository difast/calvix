#!/usr/bin/env python3
"""
Скрипт для добавления нового бизнеса в БД
Запуск: python scripts/add_business.py
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.repositories import BusinessRepository
from bot.models.database import AsyncSessionLocal


async def add_business():
    print("🆕 Добавление нового бизнеса\n")
    
    bot_token = input("Токен Telegram бота: ").strip()
    name = input("Название бизнеса: ").strip()
    manager_link = input("Ссылка на менеджера (например @username): ").strip() or "@akovpyat"
    
    print("\n📝 Введите промпт для AI (на русском, подробно):")
    print("Пример: Ты продаёшь стройматериалы...")
    system_prompt = input("Промпт: ").strip()
    
    if not all([bot_token, name, system_prompt]):
        print("❌ Ошибка: все поля обязательны")
        return
    
    repo = BusinessRepository()
    business = await repo.add(bot_token, name, system_prompt, manager_link)
    
    print(f"\n✅ Бизнес добавлен! ID: {business.id}")
    print(f"Бот запустится после команды /reload в админ-боте")


if __name__ == "__main__":
    asyncio.run(add_business())