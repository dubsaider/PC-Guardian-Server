"""
Управление сессиями базы данных
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Generator

# Создаем базовый класс для моделей
Base = declarative_base()

# Настройка подключения к БД
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///pc_guardian.db')

# Оптимизация для SQLite: timeout для избежания блокировок
if 'sqlite' in DATABASE_URL:
    connect_args = {
        "check_same_thread": False,
        "timeout": 20.0,  # Таймаут для операций (20 секунд)
    }
    # Используем WAL режим для лучшей параллельности
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False
    )
    # Включаем WAL режим после создания engine для лучшей параллельности
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """Получить сессию БД (dependency injection для FastAPI)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
