#!/bin/bash
set -e

echo "🔄 Применение миграций..."
alembic upgrade head

echo "🚀 Запуск бота..."
exec python -m bot.main