#!/bin/bash
set -e

# Инициализация БД при первом запуске
if [ ! -f /app/data/pc_guardian.db ]; then
    echo "Инициализация базы данных..."
    python init_db.py
fi

# Запуск приложения
exec "$@"

