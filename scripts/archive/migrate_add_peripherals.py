"""
Скрипт миграции для добавления полей agent_version и peripherals
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
    """Добавить новые поля в таблицу pc_configurations"""
    db = SessionLocal()
    try:
        # Проверяем, существует ли поле agent_version
        result = db.execute(text("PRAGMA table_info(pc_configurations)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'agent_version' not in columns:
            print("Добавление поля agent_version...")
            db.execute(text("ALTER TABLE pc_configurations ADD COLUMN agent_version VARCHAR(50)"))
            db.commit()
            print("✓ Поле agent_version добавлено")
        else:
            print("✓ Поле agent_version уже существует")
        
        if 'peripherals' not in columns:
            print("Добавление поля peripherals...")
            db.execute(text("ALTER TABLE pc_configurations ADD COLUMN peripherals TEXT"))
            db.commit()
            print("✓ Поле peripherals добавлено")
        else:
            print("✓ Поле peripherals уже существует")
        
        print("\nМиграция завершена успешно!")
        
    except Exception as e:
        db.rollback()
        print(f"Ошибка при миграции: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

