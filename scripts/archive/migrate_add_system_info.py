"""
Скрипт миграции для добавления поля system_info
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Устанавливаем путь к БД перед импортом database
db_path = project_root / "data" / "pc_guardian.db"
# Создаем директорию data, если её нет
db_path.parent.mkdir(exist_ok=True)
# Устанавливаем DATABASE_URL для использования БД из директории data
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path.resolve()}'

from sqlalchemy import text
from infrastructure.database.session import engine, SessionLocal

def migrate():
    """Добавить поле system_info в таблицу pc_configurations"""
    db = SessionLocal()
    try:
        # Проверяем, существует ли поле system_info
        result = db.execute(text("PRAGMA table_info(pc_configurations)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'system_info' not in columns:
            print("Добавление поля system_info...")
            db.execute(text("ALTER TABLE pc_configurations ADD COLUMN system_info TEXT"))
            db.commit()
            print("✓ Поле system_info добавлено")
        else:
            print("✓ Поле system_info уже существует")
        
        print("\nМиграция завершена успешно!")
        
    except Exception as e:
        db.rollback()
        print(f"Ошибка при миграции: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

