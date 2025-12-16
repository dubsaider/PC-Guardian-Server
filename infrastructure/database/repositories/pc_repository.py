"""
Репозиторий для работы с ПК
"""
from sqlalchemy.orm import Session
from sqlalchemy.orm.query import Query
from typing import Optional, List
from datetime import datetime, timedelta

from infrastructure.database.models import PC
from infrastructure.database.repositories.base_repository import BaseRepository


class PCRepository(BaseRepository):
    """Репозиторий для работы с ПК"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_by_id(self, pc_id: str) -> Optional[PC]:
        """Найти ПК по ID"""
        return self.db.query(PC).filter(PC.pc_id == pc_id).first()
    
    def create(self, pc: PC) -> PC:
        """Создать новый ПК"""
        self.db.add(pc)
        self.db.flush()
        return pc
    
    def update(self, pc: PC) -> PC:
        """Обновить ПК"""
        self.db.flush()
        return pc
    
    def _apply_filters(
        self,
        query: Query,
        status: Optional[str] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        location: Optional[str] = None,
        search: Optional[str] = None
    ) -> Query:
        """
        Применить фильтры к запросу (общая логика для find_all и count_all)
        
        Args:
            query: SQLAlchemy запрос
            status: Фильтр по статусу
            building: Фильтр по корпусу (уже нормализован)
            floor: Фильтр по этажу (уже нормализован)
            location: Фильтр по локации (уже нормализован)
            search: Поисковый запрос (уже нормализован)
            
        Returns:
            Запрос с примененными фильтрами
        """
        # Фильтр по статусу (специфичен для PC)
        if status:
            query = query.filter(PC.status == status)
        
        # Используем общие методы из базового класса
        query = self._apply_pc_location_filters(query, building, floor, location)
        query = self._apply_pc_search_filter(query, search)
        
        return query
    
    def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        location: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = 'asc'
    ) -> List[PC]:
        """Найти все ПК с фильтрацией и сортировкой"""
        query = self.db.query(PC)
        
        # Применяем фильтры (общая логика)
        query = self._apply_filters(
            query, status, building, floor, location, search
        )
        
        # Сортировка
        if sort_by:
            sort_column = getattr(PC, sort_by, None)
            if sort_column:
                if sort_order.lower() == 'asc':
                    query = query.order_by(sort_column.asc())
                else:
                    query = query.order_by(sort_column.desc())
        else:
            # По умолчанию сортировка по hostname (ASC)
            query = query.order_by(PC.hostname.asc())
        
        return query.offset(skip).limit(limit).all()
    
    def count_all(
        self,
        status: Optional[str] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        location: Optional[str] = None,
        search: Optional[str] = None
    ) -> int:
        """Подсчитать общее количество ПК с фильтрацией"""
        query = self.db.query(PC)
        
        # Применяем фильтры (общая логика)
        query = self._apply_filters(
            query, status, building, floor, location, search
        )
        
        return query.count()
    
    def update_offline_status(self, offline_threshold_minutes: int = 10) -> None:
        """
        Обновить статус ПК на 'offline', если last_seen старше порога
        
        Args:
            offline_threshold_minutes: Порог в минутах для определения offline статуса
        """
        threshold = datetime.utcnow() - timedelta(minutes=offline_threshold_minutes)
        
        # Обновляем статус на 'offline' для ПК, которые не обновлялись дольше порога
        # но только если они еще не в статусе 'offline'
        self.db.query(PC).filter(
            PC.last_seen.isnot(None),
            PC.last_seen < threshold,
            PC.status != 'offline'
        ).update({"status": "offline"}, synchronize_session=False)
        
        self.db.commit()
