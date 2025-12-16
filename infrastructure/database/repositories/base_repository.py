"""
Базовый репозиторий с общей логикой фильтрации
"""
from typing import Optional
from sqlalchemy.orm.query import Query
from sqlalchemy import or_

from infrastructure.database.models import PC


class BaseRepository:
    """Базовый класс для репозиториев с общей логикой фильтрации"""
    
    def _apply_pc_location_filters(
        self,
        query: Query,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        location: Optional[str] = None,
        pc_model: type = PC
    ) -> Query:
        """
        Применить фильтры по локации ПК (building, floor, location)
        
        Args:
            query: SQLAlchemy запрос (должен содержать join с PC, если используется другая модель)
            building: Фильтр по корпусу (уже нормализован)
            floor: Фильтр по этажу (уже нормализован)
            location: Фильтр по локации (уже нормализован)
            pc_model: Модель PC для фильтрации (для join запросов)
            
        Returns:
            Запрос с примененными фильтрами
        """
        if building:
            # Регистронезависимый поиск по корпусу (building уже нормализован на уровне API)
            query = query.filter(pc_model.building.ilike(f"%{building}%"))
        if floor:
            # Регистронезависимый поиск по этажу (floor уже нормализован на уровне API)
            query = query.filter(pc_model.floor.ilike(f"%{floor}%"))
        if location:
            # Регистронезависимый поиск по локации (location уже нормализован на уровне API)
            query = query.filter(pc_model.location.ilike(f"%{location}%"))
        
        return query
    
    def _apply_pc_search_filter(
        self,
        query: Query,
        search: Optional[str] = None,
        pc_model: type = PC
    ) -> Query:
        """
        Применить поисковый фильтр по ПК (hostname или pc_id)
        
        Args:
            query: SQLAlchemy запрос (должен содержать join с PC, если используется другая модель)
            search: Поисковый запрос (уже нормализован)
            pc_model: Модель PC для фильтрации (для join запросов)
            
        Returns:
            Запрос с примененными фильтрами
        """
        if search:
            # Поиск по hostname или pc_id (search уже нормализован на уровне API)
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    pc_model.hostname.ilike(search_filter),
                    pc_model.pc_id.ilike(search_filter)
                )
            )
        
        return query

