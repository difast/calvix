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

BOTS = [
    {
        "token": "8849783846:AAEWdmXwfosPIjWiCS9awyAjzwGVkpqvtr0",
        "name": "Test Calvix",
        "prompt": "Ты AI-ассистент по продажам компании Calvix. Выяви потребность клиента, расскажи о продукте и запиши на консультацию. Отвечай по-русски, кратко и по делу. Не используй markdown-форматирование.",
        "welcome": "👋 Привет! Я AI-ассистент Calvix. Чем могу помочь?",
        "manager": "@akovpyat",
    },
    {
        "token": "8845056407:AAF1lBYXF68viNYfqRZrE9sOBq5FeyPeTSA",
        "name": "Test Calvix 1.1",
        "prompt": "Ты AI-ассистент по продажам компании Calvix. Выяви потребность клиента, расскажи о продукте и запиши на консультацию. Отвечай по-русски, кратко и по делу. Не используй markdown-форматирование.",
        "welcome": "👋 Привет! Я AI-ассистент Calvix. Чем могу помочь?",
        "manager": "@akovpyat",
    },
    {
        "token": "7984911223:AAEc5JDBuexInxKawqqzE3jChbmTDM_yoSc",
        "name": "Любименький Тишкин",
        "prompt": "Ты AI-ассистент по продажам. Выяви потребность клиента, расскажи о продукте и запиши на консультацию. Отвечай по-русски, кратко и по делу. Не используй markdown-форматирование.",
        "welcome": "👋 Привет! Чем могу помочь?",
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
                "UPDATE businesses SET welcome_message = $1, is_active = true "
                "WHERE bot_token = $2 AND (welcome_message IS NULL OR welcome_message = '')",
                bot["welcome"], bot["token"]
            )
            print(f'✅ Уже есть: {bot["name"]} (id={existing})')
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
