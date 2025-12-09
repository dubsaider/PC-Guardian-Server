"""
Репозиторий для работы с конфигурациями ПК
"""
from sqlalchemy.orm import Session
from typing import Optional, List

from infrastructure.database.models import PCConfiguration


class ConfigRepository:
    """Репозиторий для работы с конфигурациями ПК"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_baseline(self, pc_id: str) -> Optional[PCConfiguration]:
        """Найти эталонную конфигурацию для ПК"""
        return self.db.query(PCConfiguration).filter_by(
            pc_id=pc_id,
            is_baseline=True
        ).first()
    
    def create(self, config: PCConfiguration) -> PCConfiguration:
        """Создать новую конфигурацию"""
        self.db.add(config)
        self.db.flush()
        return config
    
    def update_baseline(self, pc_id: str, config: PCConfiguration) -> None:
        """Установить конфигурацию как эталонную"""
        # Снимаем флаг эталонной со всех старых
        self.db.query(PCConfiguration).filter_by(
            pc_id=pc_id,
            is_baseline=True
        ).update({"is_baseline": False})
        
        # Устанавливаем новую эталонную
        config.is_baseline = True



