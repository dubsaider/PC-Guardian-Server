"""
Миграция: Добавление поля email_grouping_enabled в таблицу alert_rules
"""
import sqlite3
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infrastructure.database.session import engine, Base
from infrastructure.database.models import AlertRule
from sqlalchemy import text


def migrate():
    """Добавить поле email_grouping_enabled в таблицу alert_rules"""
    print("Начало миграции: добавление поля email_grouping_enabled...")
    
    # Проверяем, существует ли уже поле
    with engine.connect() as conn:
        # Получаем информацию о таблице
        result = conn.execute(text("PRAGMA table_info(alert_rules)"))
        columns = [row[1] for row in result]
        
        if 'email_grouping_enabled' in columns:
            print("Поле email_grouping_enabled уже существует, миграция не требуется")
            return
        
        print("Добавление поля email_grouping_enabled...")
        
        # Добавляем поле (по умолчанию True для существующих правил)
        conn.execute(text("ALTER TABLE alert_rules ADD COLUMN email_grouping_enabled BOOLEAN DEFAULT 1 NOT NULL"))
        
        conn.commit()
        print("Миграция завершена успешно")


if __name__ == '__main__':
    migrate()


