"""
Репозиторий для работы с ПК
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.orm.query import Query
from typing import Optional, List
from datetime import datetime

from infrastructure.database.models import PC, PCCurrentConfiguration
from common.utils import find_pc_ids_by_ip_search


class PCRepository:
    """Репозиторий для работы с ПК в базе данных"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_by_id(self, pc_id: str) -> Optional[PC]:
        """Найти ПК по ID"""
        return self.db.query(PC).filter(PC.pc_id == pc_id).first()
    
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
        # Фильтры
        if status:
            query = query.filter(PC.status == status)
        if building:
            # Регистронезависимый поиск по корпусу
            query = query.filter(PC.building.ilike(f"%{building}%"))
        if floor:
            # Регистронезависимый поиск по этажу
            query = query.filter(PC.floor.ilike(f"%{floor}%"))
        if location:
            # Регистронезависимый поиск по локации
            query = query.filter(PC.location.ilike(f"%{location}%"))
        if search:
            # Поиск по hostname, pc_id или IP-адресам (подстрока)
            # search уже нормализован к нижнему регистру на уровне API
            search_filter = f"%{search}%"
            
            # Используем утилиту для поиска PC по IP-адресам
            matching_pc_ids = find_pc_ids_by_ip_search(
                self.db,
                PCCurrentConfiguration,
                search
            )
            
            # Строим фильтр: hostname, pc_id или IP-адреса
            # Используем ilike для регистронезависимого поиска (search уже нормализован)
            filters = [
                PC.hostname.ilike(search_filter),
                PC.pc_id.ilike(search_filter)
            ]
            
            if matching_pc_ids:
                filters.append(PC.pc_id.in_(matching_pc_ids))
            
            query = query.filter(or_(*filters))
        
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
        query = self._apply_filters(query, status, building, floor, location, search)
        
        # Сортировка
        if sort_by:
            sort_column = getattr(PC, sort_by, None)
            if sort_column:
                if sort_order.lower() == 'desc':
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())
        else:
            # По умолчанию сортировка по hostname
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
        query = self._apply_filters(query, status, building, floor, location, search)
        
        return query.count()
    
    def create(self, pc: PC) -> PC:
        """Создать новый ПК"""
        self.db.add(pc)
        self.db.flush()
        return pc
    
    def update(self, pc: PC) -> PC:
        """Обновить ПК"""
        self.db.flush()
        return pc
    
    def update_offline_status(self, offline_threshold_minutes: int = 10) -> int:
        """Обновить статус ПК на 'offline' если они не были в сети дольше порога"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Проблема с временными зонами: время в БД может храниться в локальном времени пользователя,
        # а контейнер работает в UTC. Используем абсолютное сравнение времени
        # Получаем все ПК и сравниваем время вручную
        now_utc = datetime.utcnow()
        threshold_minutes = offline_threshold_minutes
        
        # Получаем все ПК, которые не имеют статус 'offline'
        all_pcs = self.db.query(PC).filter(
            PC.last_seen.isnot(None),
            PC.status != 'offline'
        ).all()
        
        count = 0
        for pc in all_pcs:
            if pc.last_seen:
                # Вычисляем разницу времени между текущим UTC и last_seen
                time_diff = now_utc - pc.last_seen
                minutes_diff = time_diff.total_seconds() / 60
                
                # Если разница отрицательная, значит last_seen в будущем относительно UTC
                # Это означает, что время в БД хранится в локальной временной зоне (UTC+10)
                # Преобразуем: last_seen_utc = last_seen - 10 часов
                # Реальная разница = now_utc - (last_seen - 10ч) = now_utc - last_seen + 600 мин
                if minutes_diff < 0:
                    # Корректируем разницу: добавляем 10 часов (600 минут)
                    minutes_diff = minutes_diff + 600
                    logger.debug(f"ПК {pc.hostname}: время в локальной зоне, скорректировано")
                
                # Если последний контакт был больше threshold минут назад
                if minutes_diff > threshold_minutes:
                    old_status = pc.status
                    pc.status = 'offline'
                    logger.info(
                        f"Обновлен статус ПК {pc.pc_id} ({pc.hostname}) "
                        f"с '{old_status}' на 'offline' "
                        f"(последний контакт: {pc.last_seen}, прошло: {minutes_diff:.1f} минут)"
                    )
                    count += 1
        
        if count > 0:
            try:
                self.db.commit()
                logger.info(f"Обновлено статусов ПК на 'offline': {count}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении статусов ПК: {e}")
                self.db.rollback()
                raise
        
        return count

