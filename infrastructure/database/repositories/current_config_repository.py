"""
Репозиторий для работы с текущим состоянием конфигураций ПК
"""
from sqlalchemy.orm import Session
from typing import Optional

from infrastructure.database.models import PCCurrentConfiguration


class CurrentConfigRepository:
    """Репозиторий для работы с текущим состоянием конфигураций ПК"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_by_pc_id(self, pc_id: str) -> Optional[PCCurrentConfiguration]:
        """Найти текущее состояние конфигурации для ПК"""
        return self.db.query(PCCurrentConfiguration).filter_by(pc_id=pc_id).first()
    
    def find_all(self, pc_ids: list[str] = None) -> list[PCCurrentConfiguration]:
        """Найти текущее состояние для списка ПК или всех ПК"""
        query = self.db.query(PCCurrentConfiguration)
        if pc_ids:
            query = query.filter(PCCurrentConfiguration.pc_id.in_(pc_ids))
        return query.all()
    
    def create_or_update(self, current_config: PCCurrentConfiguration) -> PCCurrentConfiguration:
        """Создать или обновить текущее состояние конфигурации"""
        existing = self.find_by_pc_id(current_config.pc_id)
        if existing:
            # Обновляем существующую запись
            for key, value in current_config.to_dict().items():
                if key != 'pc_id':  # Не обновляем первичный ключ
                    setattr(existing, key, getattr(current_config, key, None))
            existing.updated_at = current_config.updated_at
            return existing
        else:
            # Создаем новую запись
            self.db.add(current_config)
            self.db.flush()
            return current_config
    
