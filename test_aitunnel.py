"""
Тестовый скрипт для проверки подключения к Aitunnel
Запустите перед запуском бота
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Читаем настройки
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.aitunnel.ru/v1")
MODEL = os.getenv("AI_MODEL", "claude-haiku-4.5")

print("🔍 Тестирование подключения к Aitunnel...")
print(f"📍 Base URL: {BASE_URL}")
print(f"🤖 Модель: {MODEL}")
print(f"🔑 API Key: {API_KEY[:20]}..." if API_KEY else "❌ API KEY не найден!")
print()

if not API_KEY:
    print("❌ Ошибка: OPENAI_API_KEY не найден в .env файле")
    print("Создайте файл .env с вашим ключом Aitunnel")
    exit(1)

# Список моделей для тестирования
models_to_try = [
    MODEL,  # Ваша модель из .env
    "claude-haiku-4.5",
    "anthropic/claude-haiku-4.5",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
    "gpt-4o-mini",  # запасной вариант для проверки
]

try:
    # Создаем клиент (новый синтаксис для openai 1.x)
    print("📡 Создание клиента...")
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=30.0,  # Таймаут 30 секунд
        max_retries=2,  # 2 попытки при ошибке
    )
    
    # Пробуем разные модели
    success = False
    for model_name in models_to_try:
        print(f"\n🔄 Пробуем модель: {model_name}")
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": "Ответь одним словом: Привет! Ты работаешь?"}
                ],
                max_tokens=50,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content
            print(f"✅ УСПЕХ! Модель {model_name} отвечает:")
            print(f"   {answer}")
            success = True
            
            # Обновляем .env файл с правильной моделью
            if model_name != MODEL:
                print(f"\n💡 Совет: Обновите AI_MODEL в .env на: {model_name}")
                
                # Автоматически обновляем .env
                env_path = ".env"
                if os.path.exists(env_path):
                    with open(env_path, 'r') as f:
                        lines = f.readlines()
                    
                    with open(env_path, 'w') as f:
                        for line in lines:
                            if line.startswith("AI_MODEL="):
                                f.write(f"AI_MODEL={model_name}\n")
                            else:
                                f.write(line)
                    print(f"✅ .env файл обновлен! Теперь используется {model_name}")
            
            break
            
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg:
                print(f"❌ Ошибка авторизации для {model_name} (неверный ключ?)")
            elif "404" in error_msg:
                print(f"❌ Модель {model_name} не найдена")
            elif "timed out" in error_msg.lower():
                print(f"❌ Таймаут для {model_name}")
            else:
                print(f"❌ Ошибка для {model_name}: {error_msg[:100]}")
            continue
    
    if not success:
        print("\n❌ НИ ОДНА МОДЕЛЬ НЕ СРАБОТАЛА")
        print("\nПроверьте:")
        print("1. API ключ (должен начинаться с sk-aitunnel-)")
        print("2. Base URL (должен быть https://api.aitunnel.ru/v1)")
        print("3. Интернет соединение")
        print("4. Баланс на аккаунте Aitunnel")
        exit(1)
    
    print("\n🎉 Тест пройден! Бот будет работать.")
    
except Exception as e:
    print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
    print("\nВозможные причины:")
    print("1. Не установлена библиотека openai: pip install openai")
    print("2. Проблемы с сетью / прокси")
    print("3. Неверный формат API ключа")
    print("4. Aitunnel сервис недоступен")
    
    print("\nПопробуйте обновить библиотеку:")
    print("  pip install --upgrade openai")