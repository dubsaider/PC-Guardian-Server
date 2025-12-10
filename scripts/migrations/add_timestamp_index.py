#!/usr/bin/env python3
"""
Миграция: добавление индекса на timestamp в таблице pc_configurations
"""
import sys
import os

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from infrastructure.database.session import SessionLocal, engine
from sqlalchemy import text

def migrate():
    """Добавить индекс на timestamp"""
    db = SessionLocal()
    try:
        print("Добавление индекса на timestamp в таблице pc_configurations...")
        
        # Проверяем, существует ли индекс
        result = db.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' 
            AND name='ix_pc_configurations_timestamp'
        """))
        
        if result.fetchone():
            print("Индекс уже существует, пропускаем миграцию")
        else:
            # Создаем индекс
            db.execute(text("""
                CREATE INDEX ix_pc_configurations_timestamp 
                ON pc_configurations(timestamp)
            """))
            db.commit()
            print("Индекс успешно создан")
        
    except Exception as e:
        db.rollback()
        print(f"Ошибка при создании индекса: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    migrate()


