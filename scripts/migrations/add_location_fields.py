"""
Миграция: Добавление полей локации в таблицу pcs
"""
import sqlite3
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infrastructure.database.session import engine, Base
from infrastructure.database.models import PC
from sqlalchemy import text


def migrate():
    """Добавить поля location, building, floor в таблицу pcs"""
    print("Начало миграции: добавление полей локации...")
    
    # Проверяем, существуют ли уже поля
    with engine.connect() as conn:
        # Получаем информацию о таблице
        result = conn.execute(text("PRAGMA table_info(pcs)"))
        columns = [row[1] for row in result]
        
        if 'location' in columns:
            print("Поля локации уже существуют, миграция не требуется")
            return
        
        print("Добавление полей location, building, floor...")
        
        # Добавляем поля
        conn.execute(text("ALTER TABLE pcs ADD COLUMN location VARCHAR(255)"))
        conn.execute(text("ALTER TABLE pcs ADD COLUMN building VARCHAR(50)"))
        conn.execute(text("ALTER TABLE pcs ADD COLUMN floor VARCHAR(50)"))
        
        # Создаем индексы
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pcs_location ON pcs(location)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pcs_building ON pcs(building)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pcs_floor ON pcs(floor)"))
        
        conn.commit()
        print("Миграция завершена успешно")


if __name__ == '__main__':
    migrate()


