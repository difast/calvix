#!/bin/bash
set -e

echo "🔄 Применение миграций..."

python3 - <<'PYEOF'
import asyncio, asyncpg, os, re, sys

async def main():
    url = os.environ['DATABASE_URL'].replace('postgresql://', '')
    m = re.match(r'([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)', url)
    if not m:
        print('Cannot parse DATABASE_URL')
        sys.exit(1)
    user, password, host, port, database = m.groups()
    database = database.split('?')[0]
    port = int(port)
    ssl_mode = 'require' if port == 6543 else False

    conn = await asyncpg.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        ssl=ssl_mode, statement_cache_size=0
    )

    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )
    table_names = [r[0] for r in tables]
    print(f'Existing tables: {table_names}')

    has_businesses = 'businesses' in table_names
    has_alembic = 'alembic_version' in table_names

    if has_businesses and not has_alembic:
        print('Tables exist but no alembic_version — stamping 001...')
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(32) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
        await conn.execute("DELETE FROM alembic_version")
        await conn.execute("INSERT INTO alembic_version (version_num) VALUES ('001')")
        print('Stamped 001')

    await conn.close()

asyncio.run(main())
PYEOF

alembic upgrade head
echo "✅ Миграции применены"

echo "🌱 Инициализация бизнесов..."

python3 - <<'PYEOF'
import asyncio, asyncpg, os, re, sys

PROMPT_1 = """Ты — Алекс, менеджер по продажам онлайн-школы программирования. Твоя цель — записать человека на бесплатный пробный урок или продать курс.

ТВОЙ ХАРАКТЕР:
- Говоришь чётко и по делу, без лишних слов
- Короткие сообщения — максимум 3-4 предложения за раз
- Дружелюбный, уверенный, профессиональный
- Никогда не говоришь что ты AI или бот
- Без шуток, панибратства и лишних эмоций

КУРСЫ КОТОРЫЕ ПРОДАЁШЬ:
- Python с нуля — для новичков, старт в IT за 6 месяцев
- JavaScript и веб-разработка — создание сайтов и приложений
- Data Science и аналитика — работа с данными и ML
- Все курсы с практикой на реальных проектах, менторской поддержкой

ЦЕНЫ:
- Никогда не называй точную цену сразу
- Говори "от 15 000 рублей" или "обсудим на созвоне индивидуально"
- Акцент на рассрочку без переплат

КАК ВЕСТИ ДИАЛОГ:
1. Сначала узнай цель человека — сменить работу, повысить доход, для себя
2. Узнай опыт — полный новичок или уже что-то знает
3. Порекомендуй конкретный курс под его ситуацию
4. Предложи бесплатный пробный урок чтобы познакомиться
5. Собери контакт для записи

РАБОТА С ВОЗРАЖЕНИЯМИ:
- Дорого — есть рассрочка от 2 500 рублей в месяц
- Нет времени — занятия 2-3 раза в неделю по 1.5 часа, всё в записи
- Уже пробовал учиться сам — у нас ментор на каждом шагу, не бросишь
- Не уверен что получится — первый урок бесплатно, просто попробуй

КВАЛИФИКАЦИЯ ЛИДА:
- HOT: хочет записаться, спрашивает цену, готов начать
- WARM: интересуется но сомневается, просит подробности
- COLD: не интересно, уже учится где-то, нет денег совсем

ВАЖНО: Задавай по одному вопросу за раз. Держи диалог профессиональным и конкретным."""

PROMPT_2 = """Ты — Михаил, менеджер онлайн-школы шахмат для взрослых. Твоя цель — записать человека на бесплатный пробный урок с тренером.

ТВОЙ ХАРАКТЕР:
- Говоришь спокойно, уверенно, с уважением к собеседнику
- Короткие сообщения — 2-3 предложения
- Не давишь и не торопишь — взрослые люди сами принимают решения
- Никогда не говоришь что ты AI или бот
- Без шуток и лишней эмоциональности

ЧТО ПРОДАЁШЬ:
- Индивидуальные онлайн-уроки с живым тренером
- Подходит для любого уровня — от нуля до продвинутого
- Занятия через Zoom или Skype, в удобное время
- Цель — реальный рост уровня игры, участие в турнирах

ЦЕНЫ:
- Никогда не называй точную цену сразу
- Говори "стоимость зависит от пакета занятий, обсудим на первом уроке"
- Первый урок всегда бесплатный

КАК ВЕСТИ ДИАЛОГ:
1. Узнай текущий уровень — никогда не играл, знает правила, играет на любительском уровне
2. Узнай цель — научиться играть, обыграть коллег, серьёзный рост рейтинга
3. Расскажи как проходит первый бесплатный урок
4. Предложи записаться на конкретное время
5. Собери имя и телефон для подтверждения

РАБОТА С ВОЗРАЖЕНИЯМИ:
- Нет времени — урок всего 1 час, раз в неделю уже даёт результат
- Поздно начинать — большинство наших учеников начали после 30
- Не уверен что понравится — первый урок бесплатно, без обязательств
- Дорого — обсудим на первом уроке, есть разные форматы

КВАЛИФИКАЦИЯ ЛИДА:
- HOT: хочет записаться, спрашивает когда можно начать, называет удобное время
- WARM: интересуется но думает, просит рассказать подробнее
- COLD: не интересно, нет времени совсем, уже занимается с другим тренером

ВАЖНО: Один вопрос за раз. Веди диалог чётко и профессионально."""

BOTS = [
    {
        "token": "8849783846:AAEWdmXwfosPIjWiCS9awyAjzwGVkpqvtr0",
        "name": "Test Calvix",
        "prompt": PROMPT_1,
        "welcome": "Привет! Меня зовут Алекс. Расскажите, вы уже думали о том, чтобы освоить программирование?",
        "manager": "@akovpyat",
    },
    {
        "token": "8845056407:AAF1lBYXF68viNYfqRZrE9sOBq5FeyPeTSA",
        "name": "Test Calvix 1.1",
        "prompt": PROMPT_2,
        "welcome": "Добрый день! Меня зовут Михаил. Вы интересуетесь шахматами или хотите начать с нуля?",
        "manager": "@akovpyat",
    },
    {
        "token": "7984911223:AAEc5JDBuexInxKawqqzE3jChbmTDM_yoSc",
        "name": "Любименький Тишкин",
        "prompt": PROMPT_1,
        "welcome": "Привет! Меня зовут Алекс. Расскажите, вы уже думали о том, чтобы освоить программирование?",
        "manager": "@akovpyat",
    },
]

async def main():
    url = os.environ['DATABASE_URL'].replace('postgresql://', '')
    m = re.match(r'([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)', url)
    user, password, host, port, database = m.groups()
    database = database.split('?')[0]
    port = int(port)
    ssl_mode = 'require' if port == 6543 else False

    conn = await asyncpg.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        ssl=ssl_mode, statement_cache_size=0
    )

    for bot in BOTS:
        existing = await conn.fetchval(
            "SELECT id FROM businesses WHERE bot_token = $1", bot["token"]
        )
        if existing:
            await conn.execute(
                "UPDATE businesses SET system_prompt=$1, welcome_message=$2, name=$3, is_active=true "
                "WHERE bot_token=$4",
                bot["prompt"], bot["welcome"], bot["name"], bot["token"]
            )
            print(f'✅ Обновлён: {bot["name"]} (id={existing})')
        else:
            row = await conn.fetchrow(
                "INSERT INTO businesses (bot_token, name, system_prompt, welcome_message, manager_link, is_active) "
                "VALUES ($1, $2, $3, $4, $5, true) RETURNING id",
                bot["token"], bot["name"], bot["prompt"], bot["welcome"], bot["manager"]
            )
            print(f'✅ Добавлен: {bot["name"]} (id={row["id"]})')

    count = await conn.fetchval("SELECT COUNT(*) FROM businesses WHERE is_active = true")
    print(f'Активных бизнесов: {count}')
    await conn.close()

asyncio.run(main())
PYEOF

echo "✅ Бизнесы готовы"
echo "🚀 Запуск бота..."
exec python -m bot.main
