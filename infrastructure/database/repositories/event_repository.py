"""
Репозиторий для работы с событиями изменений
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
from datetime import datetime, timedelta

from infrastructure.database.models import ChangeEvent, PC


class EventRepository:
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
        
        # Фильтры
        if pc_id:
            query = query.filter(ChangeEvent.pc_id == pc_id)
        if component_type:
            query = query.filter(ChangeEvent.component_type == component_type)
        if event_type:
            query = query.filter(ChangeEvent.event_type == event_type)
        if building:
            query = query.filter(PC.building == building)
        if floor:
            query = query.filter(PC.floor == floor)
        if location:
            query = query.filter(PC.location == location)
        if date_from:
            query = query.filter(ChangeEvent.timestamp >= date_from)
        if date_to:
            query = query.filter(ChangeEvent.timestamp <= date_to)
        if search:
            # Поиск по hostname или pc_id
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    PC.hostname.ilike(search_filter),
                    ChangeEvent.pc_id.ilike(search_filter)
                )
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
        
        # Фильтры
        if pc_id:
            query = query.filter(ChangeEvent.pc_id == pc_id)
        if component_type:
            query = query.filter(ChangeEvent.component_type == component_type)
        if event_type:
            query = query.filter(ChangeEvent.event_type == event_type)
        if building:
            query = query.filter(PC.building == building)
        if floor:
            query = query.filter(PC.floor == floor)
        if location:
            query = query.filter(PC.location == location)
        if date_from:
            query = query.filter(ChangeEvent.timestamp >= date_from)
        if date_to:
            query = query.filter(ChangeEvent.timestamp <= date_to)
        if search:
            # Поиск по hostname или pc_id
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    PC.hostname.ilike(search_filter),
                    ChangeEvent.pc_id.ilike(search_filter)
                )
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



