#!/usr/bin/env python3
"""
Миграция: создание таблицы pc_current_configurations для хранения текущего состояния ПК
"""
import sys
import os

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from infrastructure.database.session import SessionLocal, engine
from sqlalchemy import text

def migrate():
    """Создать таблицу pc_current_configurations и заполнить её данными из последних конфигураций"""
    db = SessionLocal()
    try:
        print("Создание таблицы pc_current_configurations...")
        
        # Проверяем, существует ли таблица
        result = db.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name='pc_current_configurations'
        """))
        
        if result.fetchone():
            print("Таблица уже существует, пропускаем создание")
        else:
            # Создаем таблицу
            db.execute(text("""
                CREATE TABLE pc_current_configurations (
                    pc_id VARCHAR(255) PRIMARY KEY NOT NULL,
                    updated_at DATETIME NOT NULL,
                    agent_version VARCHAR(50),
                    motherboard TEXT,
                    cpu TEXT,
                    ram_modules TEXT,
                    storage_devices TEXT,
                    gpu TEXT,
                    network_adapters TEXT,
                    psu TEXT,
                    peripherals TEXT,
                    system_info TEXT,
                    FOREIGN KEY (pc_id) REFERENCES pcs(pc_id)
                )
            """))
            
            # Создаем индексы
            db.execute(text("""
                CREATE INDEX ix_pc_current_configurations_updated_at 
                ON pc_current_configurations(updated_at)
            """))
            
            db.commit()
            print("Таблица успешно создана")
        
        # Заполняем таблицу данными из последних конфигураций
        print("Заполнение таблицы данными из последних конфигураций...")
        
        # SQLite не поддерживает ROW_NUMBER(), используем подзапрос
        # Получаем последние конфигурации для каждого ПК
        result = db.execute(text("""
            INSERT OR REPLACE INTO pc_current_configurations 
            (pc_id, updated_at, agent_version, motherboard, cpu, ram_modules, 
             storage_devices, gpu, network_adapters, psu, peripherals, system_info)
            SELECT 
                c1.pc_id,
                c1.timestamp as updated_at,
                c1.agent_version,
                c1.motherboard,
                c1.cpu,
                c1.ram_modules,
                c1.storage_devices,
                c1.gpu,
                c1.network_adapters,
                c1.psu,
                c1.peripherals,
                c1.system_info
            FROM pc_configurations c1
            INNER JOIN (
                SELECT pc_id, MAX(timestamp) as max_timestamp
                FROM pc_configurations
                GROUP BY pc_id
            ) c2 ON c1.pc_id = c2.pc_id AND c1.timestamp = c2.max_timestamp
            INNER JOIN (
                SELECT pc_id, timestamp, MAX(id) as max_id
                FROM pc_configurations
                GROUP BY pc_id, timestamp
            ) c3 ON c1.pc_id = c3.pc_id AND c1.timestamp = c3.timestamp AND c1.id = c3.max_id
        """))
        
        db.commit()
        count = result.rowcount if hasattr(result, 'rowcount') else 0
        print(f"Заполнено {count} записей")
        
    except Exception as e:
        db.rollback()
        print(f"Ошибка при миграции: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    migrate()

