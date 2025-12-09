"""
Репозиторий для работы с ПК
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from datetime import datetime

from infrastructure.database.models import PC, PCCurrentConfiguration


class PCRepository:
    """Репозиторий для работы с ПК в базе данных"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_by_id(self, pc_id: str) -> Optional[PC]:
        """Найти ПК по ID"""
        return self.db.query(PC).filter(PC.pc_id == pc_id).first()
    
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
        
        # Фильтры
        if status:
            query = query.filter(PC.status == status)
        if building:
            query = query.filter(PC.building == building)
        if floor:
            query = query.filter(PC.floor == floor)
        if location:
            query = query.filter(PC.location == location)
        if search:
            # Поиск по hostname или pc_id
            search_filter = f"%{search}%"
            query = query.filter(
                (PC.hostname.ilike(search_filter)) | 
                (PC.pc_id.ilike(search_filter))
            )
        
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
        
        # Фильтры
        if status:
            query = query.filter(PC.status == status)
        if building:
            query = query.filter(PC.building == building)
        if floor:
            query = query.filter(PC.floor == floor)
        if location:
            query = query.filter(PC.location == location)
        if search:
            # Поиск по hostname, pc_id или IP-адресам (подстрока)
            search_filter = f"%{search}%"
            
            # Оптимизация: используем таблицу текущих конфигураций для поиска по IP
            # Получаем список PC ID, у которых в текущей конфигурации есть IP-адреса, содержащие подстроку
            current_configs = self.db.query(PCCurrentConfiguration).filter(
                PCCurrentConfiguration.network_adapters.isnot(None)
            ).all()
            
            # Собираем список PC ID, где IP-адреса содержат подстроку
            matching_pc_ids = []
            for current_config in current_configs:
                try:
                    if current_config.network_adapters:
                        network_data = current_config.get_component('network_adapters')
                        if isinstance(network_data, list):
                            for adapter in network_data:
                                if isinstance(adapter, dict):
                                    ip_addresses = adapter.get('ip_addresses', [])
                                    if ip_addresses:
                                        for ip in ip_addresses:
                                            if search.lower() in ip.lower():
                                                matching_pc_ids.append(current_config.pc_id)
                                                break
                except:
                    continue
            
            # Строим фильтр: hostname, pc_id или IP-адреса
            filters = [
                PC.hostname.ilike(search_filter),
                PC.pc_id.ilike(search_filter)
            ]
            
            if matching_pc_ids:
                filters.append(PC.pc_id.in_(matching_pc_ids))
            
            query = query.filter(or_(*filters))
        
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

