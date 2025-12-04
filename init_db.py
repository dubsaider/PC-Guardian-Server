"""
Скрипт инициализации базы данных
"""
from database import Base, engine, SessionLocal, User
from auth import get_password_hash

def init_db():
    """Инициализировать базу данных"""
    # Создаем таблицы
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Проверяем, есть ли уже пользователи
        if db.query(User).count() == 0:
            # Создаем администратора по умолчанию
            admin = User(
                username="admin",
                email="admin@pc-guardian.local",
                password_hash=get_password_hash("admin"),
                role="admin"
            )
            db.add(admin)
            
            # Создаем пользователя для просмотра
            viewer = User(
                username="viewer",
                email="viewer@pc-guardian.local",
                password_hash=get_password_hash("viewer"),
                role="viewer"
            )
            db.add(viewer)
            
            db.commit()
            print("Созданы пользователи по умолчанию:")
            print("  admin/admin (администратор)")
            print("  viewer/viewer (просмотр)")
        else:
            print("База данных уже инициализирована")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()

