#!/bin/bash
set -e

echo "🔄 Применение миграций..."

python3 - <<'PYEOF'
import asyncio, asyncpg, os, re, subprocess, sys

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

    # Проверяем существуют ли основные таблицы
    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )
    table_names = [r[0] for r in tables]
    print(f'Existing tables: {table_names}')

    has_businesses = 'businesses' in table_names
    has_alembic = 'alembic_version' in table_names

    if has_businesses and not has_alembic:
        # Таблицы уже созданы вручную/ранее — помечаем 001 как выполненную
        print('Tables exist but no alembic_version — stamping 001...')
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
        # Удалим если есть старое значение и установим 001
        await conn.execute("DELETE FROM alembic_version")
        await conn.execute("INSERT INTO alembic_version (version_num) VALUES ('001')")
        print('Stamped 001')

    await conn.close()

asyncio.run(main())
PYEOF

# Применяем все новые миграции
alembic upgrade head

echo "✅ Миграции применены"
echo "🚀 Запуск бота..."
exec python -m bot.main
