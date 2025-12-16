"""
Репозиторий для работы с событиями изменений
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.orm.query import Query
from typing import Optional, List
from datetime import datetime, timedelta

from infrastructure.database.models import ChangeEvent, PC
from infrastructure.database.repositories.base_repository import BaseRepository


class EventRepository(BaseRepository):
    """Репозиторий для работы с событиями изменений"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_by_pc_id(
        self, 
        pc_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ChangeEvent]:
        """Найти события для ПК"""
        return self.db.query(ChangeEvent).filter(
            ChangeEvent.pc_id == pc_id
        ).order_by(ChangeEvent.timestamp.desc()).offset(skip).limit(limit).all()
    
    def count_by_pc_id(self, pc_id: str) -> int:
        """Подсчитать количество событий для ПК"""
        return self.db.query(ChangeEvent).filter(ChangeEvent.pc_id == pc_id).count()
    
    def _apply_filters(
        self,
        query: Query,
        pc_id: Optional[str] = None,
        component_type: Optional[str] = None,
        event_type: Optional[str] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        location: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None
    ) -> Query:
        """
        Применить фильтры к запросу (общая логика для find_all и count_all)
        
        Args:
            query: SQLAlchemy запрос
            pc_id: Фильтр по PC ID
            component_type: Фильтр по типу компонента
            event_type: Фильтр по типу события
            building: Фильтр по корпусу (уже нормализован)
            floor: Фильтр по этажу (уже нормализован)
            location: Фильтр по локации (уже нормализован)
            date_from: Фильтр по начальной дате
            date_to: Фильтр по конечной дате
            search: Поисковый запрос (уже нормализован)
            
        Returns:
            Запрос с примененными фильтрами
        """
        # Фильтры
        if pc_id:
            query = query.filter(ChangeEvent.pc_id == pc_id)
        if component_type:
            query = query.filter(ChangeEvent.component_type == component_type)
        if event_type:
            query = query.filter(ChangeEvent.event_type == event_type)
        # Используем общие методы из базового класса для фильтрации по PC
        query = self._apply_pc_location_filters(query, building, floor, location, pc_model=PC)
        query = self._apply_pc_search_filter(query, search, pc_model=PC)
        
        # Специфичные фильтры для событий
        if date_from:
            query = query.filter(ChangeEvent.timestamp >= date_from)
        if date_to:
            query = query.filter(ChangeEvent.timestamp <= date_to)
        
        return query
    
    def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        pc_id: Optional[str] = None,
        component_type: Optional[str] = None,
        event_type: Optional[str] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        location: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = 'desc'
    ) -> List[ChangeEvent]:
        """Найти все события с фильтрацией и сортировкой"""
        query = self.db.query(ChangeEvent).join(PC, ChangeEvent.pc_id == PC.pc_id)
        
        # Применяем фильтры (общая логика)
        query = self._apply_filters(
            query, pc_id, component_type, event_type,
            building, floor, location, date_from, date_to, search
            )
        
        # Сортировка
        if sort_by:
            sort_column = getattr(ChangeEvent, sort_by, None)
            if sort_column:
                if sort_order.lower() == 'asc':
                    query = query.order_by(sort_column.asc())
                else:
                    query = query.order_by(sort_column.desc())
        else:
            # По умолчанию сортировка по времени (DESC)
            query = query.order_by(ChangeEvent.timestamp.desc())
        
        return query.offset(skip).limit(limit).all()
    
    def count_all(
        self,
        pc_id: Optional[str] = None,
        component_type: Optional[str] = None,
        event_type: Optional[str] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        location: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None
    ) -> int:
        """Подсчитать общее количество событий с фильтрацией"""
        query = self.db.query(ChangeEvent).join(PC, ChangeEvent.pc_id == PC.pc_id)
        
        # Применяем фильтры (общая логика)
        query = self._apply_filters(
            query, pc_id, component_type, event_type,
            building, floor, location, date_from, date_to, search
            )
        
        return query.count()
    
    def count_recent(self, days: int = 7) -> int:
        """Подсчитать события за последние N дней"""
        threshold = datetime.utcnow() - timedelta(days=days)
        return self.db.query(ChangeEvent).filter(
            ChangeEvent.timestamp >= threshold
        ).count()
    
    def create(self, event: ChangeEvent) -> ChangeEvent:
        """Создать новое событие"""
        self.db.add(event)
        self.db.flush()
        return event



