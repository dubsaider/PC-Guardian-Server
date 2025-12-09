"""
Скрипт для очистки базы данных от всех данных
ВНИМАНИЕ: Удаляет все данные из всех таблиц, но сохраняет структуру БД
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Устанавливаем путь к БД перед импортом database
db_path = project_root / "data" / "pc_guardian.db"
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path.resolve()}'

from sqlalchemy import text
from infrastructure.database.session import SessionLocal, engine
from infrastructure.database.models import (
    PC,
    PCConfiguration,
    PCCurrentConfiguration,
    ChangeEvent,
    User
)


def clear_database(keep_users: bool = False):
    """
    Очистить базу данных от всех данных
    
    Args:
        keep_users: Если True, сохранить пользователей
    """
    db = SessionLocal()
    try:
        print("Начинаю очистку базы данных...")
        
        # Отключаем проверку внешних ключей для SQLite
        db.execute(text("PRAGMA foreign_keys=OFF"))
        
        # Список таблиц в порядке удаления (с учетом зависимостей)
        tables = [
            'change_events',      # События (зависят от PC)
            'pc_configurations',  # Исторические конфигурации (зависят от PC)
            'pc_current_configurations',  # Текущие конфигурации (зависят от PC)
            'pcs',               # ПК
        ]
        
        if not keep_users:
            tables.append('users')  # Пользователи (если не сохраняем)
        
        # Очищаем каждую таблицу
        for table in tables:
            try:
                count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                if count > 0:
                    db.execute(text(f"DELETE FROM {table}"))
                    print(f"✓ Удалено {count} записей из {table}")
                else:
                    print(f"  Таблица {table} уже пуста")
            except Exception as e:
                print(f"✗ Ошибка при очистке {table}: {e}")
        
        # Включаем обратно проверку внешних ключей
        db.execute(text("PRAGMA foreign_keys=ON"))
        
        # Сбрасываем автоинкременты для SQLite
        for table in tables:
            try:
                db.execute(text(f"DELETE FROM sqlite_sequence WHERE name='{table}'"))
            except:
                pass  # Игнорируем ошибки, если таблицы нет в sqlite_sequence
        
        db.commit()
        print("\n✓ База данных успешно очищена!")
        
        if keep_users:
            user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
            print(f"✓ Сохранено {user_count} пользователей")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Ошибка при очистке базы данных: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Очистка базы данных PC-Guardian')
    parser.add_argument(
        '--keep-users',
        action='store_true',
        help='Сохранить пользователей при очистке'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Подтвердить очистку (без этого запроса подтверждения)'
    )
    
    args = parser.parse_args()
    
    if not args.confirm:
        response = input("ВНИМАНИЕ: Это удалит все данные из базы данных! Продолжить? (yes/no): ")
        if response.lower() not in ['yes', 'y', 'да', 'д']:
            print("Отменено.")
            sys.exit(0)
    
    clear_database(keep_users=args.keep_users)

