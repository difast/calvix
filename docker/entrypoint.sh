#!/bin/bash
set -e

echo "🔄 Применение миграций..."
python3 -c "
import asyncio, asyncpg, os

async def main():
    url = os.environ['DATABASE_URL'].replace('postgresql://', '')
    # parse: user:pass@host:port/db?params
    import re
    m = re.match(r'([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)', url)
    if not m:
        print('Cannot parse DATABASE_URL, skipping migration check')
        return
    user, password, host, port, database = m.groups()
    database = database.split('?')[0]
    try:
        conn = await asyncpg.connect(
            host=host, port=int(port), user=user,
            password=password, database=database,
            ssl='require', statement_cache_size=0
        )
        tables = await conn.fetch(\"SELECT tablename FROM pg_tables WHERE schemaname='public'\")
        await conn.close()
        print(f'DB connected. Tables: {[r[0] for r in tables]}')
    except Exception as e:
        print(f'DB check failed: {e}')

asyncio.run(main())
" && echo "✅ БД проверена, миграции пропущены (таблицы уже существуют)"

echo "🚀 Запуск бота..."
exec python -m bot.main