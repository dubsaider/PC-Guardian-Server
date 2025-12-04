"""
Скрипт для добавления пользователя в базу данных
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import bcrypt
from database import Base, engine, SessionLocal, User

def add_user(username: str, email: str, password: str, role: str = "viewer"):
    """Добавить пользователя в БД"""
    # Создаем таблицы, если их нет
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Проверяем, существует ли пользователь
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"Пользователь {username} уже существует")
            return
        
        # Хешируем пароль напрямую через bcrypt
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
        
        # Создаем пользователя
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role
        )
        db.add(user)
        db.commit()
        
        print(f"Пользователь {username} успешно создан (роль: {role})")
    except Exception as e:
        db.rollback()
        print(f"Ошибка при создании пользователя: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        username = sys.argv[1]
        email = sys.argv[2]
        password = sys.argv[3]
        role = sys.argv[4] if len(sys.argv) > 4 else "viewer"
        add_user(username, email, password, role)
    else:
        # Создаем пользователей по умолчанию
        print("Создание пользователей по умолчанию...")
        add_user("admin", "admin@pc-guardian.local", "admin", "admin")
        add_user("viewer", "viewer@pc-guardian.local", "viewer", "viewer")
        print("\nПользователи по умолчанию:")
        print("  admin/admin (администратор)")
        print("  viewer/viewer (просмотр)")

