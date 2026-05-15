#!/bin/bash
set -e

echo "🔄 Применение миграций..."
alembic upgrade head || (echo "⚠️  Таблицы уже существуют, помечаем текущее состояние..." && alembic stamp head)

echo "🚀 Запуск бота..."
exec python -m bot.main