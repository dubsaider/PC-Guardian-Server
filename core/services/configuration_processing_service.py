"""
Сервис для обработки конфигураций ПК
Главный сервис, объединяющий всю бизнес-логику обработки конфигураций
"""
import logging
from datetime import datetime
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from common.models import PCConfiguration
from infrastructure.database.unit_of_work import UnitOfWork, unit_of_work
from infrastructure.database.models import PCConfiguration as DBPCConfiguration, PC
from infrastructure.database.models import ChangeEvent, PCCurrentConfiguration
from infrastructure.messaging.notification_service import NotificationService

from core.services.pc_service import PCService
from core.services.config_service import ConfigService
from core.services.event_service import EventService
from core.services.comparison_service import ComparisonService
from core.services.alert_service import AlertService
from common.location_parser import update_pc_location


class ConfigurationProcessingService:
    """
    Сервис для обработки входящих конфигураций ПК
    Объединяет всю бизнес-логику: регистрацию ПК, сравнение конфигураций, создание событий
    """
    
    def __init__(
        self,
        config_service: Optional[ConfigService] = None,
        comparison_service: Optional[ComparisonService] = None
    ):
        """
        Инициализация сервиса обработки конфигураций
        
        Args:
            config_service: Сервис для работы с конфигурациями (опционально, для тестирования)
            comparison_service: Сервис для сравнения конфигураций (опционально, для тестирования)
        """
        self.logger = logging.getLogger(__name__)
        self.config_service = config_service or ConfigService()
        self.comparison_service = comparison_service or ComparisonService()
    
    def process_configuration(self, config: PCConfiguration) -> None:
        """
        Обработать полученную конфигурацию ПК
        
        Главный метод, координирующий весь процесс обработки конфигурации.
        Использует Unit of Work для управления транзакциями.
        
        Args:
            config: Domain модель конфигурации ПК
        """
        with unit_of_work() as uow:
            try:
                # Инициализируем сервисы (они не зависят от БД)
                services = self._initialize_services(uow)
                pc_service = services['pc_service']
                notification_service = services['notification_service']
                
                # Логируем входящую конфигурацию
                self._log_incoming_config(config)
                
                # Подготавливаем ПК (находим/создаем и обновляем локацию)
                pc = self._prepare_pc(config, pc_service, uow)
                
                # Получаем эталонную конфигурацию
                baseline = uow.config_repository.find_baseline(pc.pc_id)
                
                # Инициализируем переменные для событий (нужны для уведомлений)
                domain_events: List = []
                db_events: List[ChangeEvent] = []
                
                if not baseline:
                    # Нет эталонной конфигурации - это новый ПК или первая конфигурация
                    self._handle_first_configuration(
                        pc, config, pc_service, uow
                    )
                else:
                    # Есть эталонная - сравниваем и создаем события
                    domain_events, db_events = self._handle_existing_configuration(
                        pc, config, baseline, pc_service, uow
                    )
                
                # Извлекаем данные для отправки уведомлений после коммита
                # Важно: извлекаем данные ДО закрытия сессии, чтобы избежать DetachedInstanceError
                pending_notifications = None
                if domain_events and db_events:
                    # Извлекаем данные из объектов PC и Event в простые структуры
                    pc_data = self._extract_pc_data(pc)
                    events_data = [self._extract_event_data(event) for event in db_events]
                    
                    # Логируем извлеченные ID для отладки
                    event_ids = [e.get('id') for e in events_data]
                    self.logger.debug(f"Извлечены данные событий для уведомлений: IDs={event_ids}")
                    
                    pending_notifications = {
                        'pc_data': pc_data,
                        'events_data': events_data,
                        'notification_service': notification_service
                    }
            
            except Exception as e:
                self.logger.error(f"Ошибка обработки конфигурации: {e}", exc_info=True)
                # Unit of Work автоматически откатит транзакцию при исключении
                raise
            else:
                # Unit of Work автоматически закоммитит транзакцию при успешном выходе
                # Отправляем уведомления после коммита (если есть события)
                if pending_notifications:
                    self._send_notifications_after_commit(
                        pending_notifications['pc_data'],
                        pending_notifications['events_data'],
                        pending_notifications['notification_service']
                    )
    
    def _initialize_services(self, uow: UnitOfWork) -> dict:
        """
        Инициализировать сервисы, необходимые для обработки
        
        Args:
            uow: Unit of Work с репозиториями
            
        Returns:
            Словарь с сервисами
        """
        pc_service = PCService(uow.pc_repository)
        alert_service = AlertService(uow.alert_rule_repository)
        notification_service = NotificationService(alert_service)
        
        return {
            'pc_service': pc_service,
            'alert_service': alert_service,
            'notification_service': notification_service
        }
    
    def _log_incoming_config(self, config: PCConfiguration) -> None:
        """Логировать информацию о входящей конфигурации"""
        self.logger.info(
            f"Processing config for {config.pc_id}: "
            f"agent_version={config.agent_version}, "
            f"network_adapters_count={len(config.network_adapters) if config.network_adapters else 0}"
        )
    
    def _prepare_pc(
        self, 
        config: PCConfiguration, 
        pc_service: PCService,
        uow: UnitOfWork
    ) -> PC:
        """
        Найти или создать ПК и обновить его локацию
        
        Args:
            config: Domain модель конфигурации
            pc_service: Сервис для работы с ПК
            uow: Unit of Work с репозиториями
            
        Returns:
            Объект ПК
        """
        last_seen_time = config.timestamp if config.timestamp else datetime.utcnow()
        
        # Находим или создаем ПК
        pc = pc_service.find_or_create_pc(
            pc_id=config.pc_id,
            hostname=config.hostname,
            last_seen=last_seen_time
        )
        
        # Обновляем локацию, если она пришла от агента
        if config.location:
            update_pc_location(pc, config.location)
        uow.pc_repository.update(pc)
        
        return pc
    
    def _handle_first_configuration(
        self,
        pc: PC,
        config: PCConfiguration,
        pc_service: PCService,
        uow: UnitOfWork
    ) -> None:
        """
        Обработать первую конфигурацию ПК (создать эталонную)
        
        Args:
            pc: Объект ПК
            config: Domain модель конфигурации
            pc_service: Сервис для работы с ПК
            uow: Unit of Work с репозиториями
        """
        # Создаем эталонную конфигурацию
        baseline_db = self.config_service.create_db_configuration(
            pc.pc_id, config, is_baseline=True
        )
        uow.config_repository.create(baseline_db)
        
        # Создаем обычную конфигурацию (для истории)
        current_db = self.config_service.create_db_configuration(
            pc.pc_id, config, is_baseline=False
        )
        uow.config_repository.create(current_db)
        
        # Создаем/обновляем текущую конфигурацию
        current_config = PCCurrentConfiguration.from_configuration(
            pc.pc_id, config
        )
        uow.current_config_repository.create_or_update(current_config)
        
        # Устанавливаем статус 'normal'
        pc_service.update_status(pc, 'normal')
        self.logger.info(f"Создана эталонная конфигурация для ПК: {config.pc_id}")
    
    def _handle_existing_configuration(
        self,
        pc: PC,
        config: PCConfiguration,
        baseline: DBPCConfiguration,
        pc_service: PCService,
        uow: UnitOfWork
    ) -> Tuple[List, List[ChangeEvent]]:
        """
        Обработать конфигурацию существующего ПК (сравнить и создать события)
        
        Args:
            pc: Объект ПК
            config: Domain модель новой конфигурации
            baseline: Эталонная конфигурация
            pc_service: Сервис для работы с ПК
            uow: Unit of Work с репозиториями
            
        Returns:
            Кортеж (domain_events, db_events)
        """
        last_seen_time = config.timestamp if config.timestamp else datetime.utcnow()
        pc_service.update_last_seen(pc, last_seen_time)
        
        # Получаем текущее состояние (если есть)
        current_state = uow.current_config_repository.find_by_pc_id(pc.pc_id)
        
        # Создаем объект новой конфигурации для сравнения
        new_config_db = self.config_service.create_db_configuration(
            pc.pc_id, config, is_baseline=False
        )
                
        # Сравниваем и создаем события
        domain_events, db_events = self._compare_and_create_events(
            pc, baseline, current_state, new_config_db, uow, pc_service
        )
        
        # Обновляем текущее состояние
        current_config = self.config_service.create_current_configuration(
            pc.pc_id, config
        )
        uow.current_config_repository.create_or_update(current_config)
        
        return domain_events, db_events
    
    def _compare_and_create_events(
        self,
        pc: PC,
        baseline: DBPCConfiguration,
        current_state: Optional,
        new_config_db: DBPCConfiguration,
        uow: UnitOfWork,
        pc_service: PCService
    ) -> Tuple[List, List[ChangeEvent]]:
        """
        Сравнить конфигурации и создать события изменений
        
        Args:
            pc: Объект ПК
            baseline: Эталонная конфигурация
            current_state: Текущее состояние (может быть None)
            new_config_db: Новая конфигурация для сравнения
            uow: Unit of Work с репозиториями
            pc_service: Сервис для работы с ПК
            
        Returns:
            Кортеж (domain_events, db_events)
        """
        domain_events: List = []
        db_events: List[ChangeEvent] = []
        
        # Определяем конфигурацию для сравнения
        if current_state:
            # Сравниваем с текущим состоянием
            from infrastructure.database.models import PCConfiguration as DBPCConfiguration
            current_state_db = DBPCConfiguration.from_current_configuration(current_state)
            domain_events = self.comparison_service.compare_configurations(
                current_state_db, new_config_db
            )
        else:
            # Нет текущего состояния - сравниваем с эталонной
            domain_events = self.comparison_service.compare_configurations(
                baseline, new_config_db
            )
        
        if domain_events:
            # Есть изменения - сохраняем их
            pc_service.update_status(pc, 'changed')
            
            # Создаем события БД
            event_service = EventService(uow.event_repository)
            db_events = event_service.create_events_from_domain(domain_events)
            
            self.logger.warning(
                f"Обнаружены изменения на ПК {pc.pc_id}: {len(domain_events)} событий"
            )
        else:
            # Нет изменений
            pc_service.update_status(pc, 'normal')
                
        return domain_events, db_events
    
    def _extract_pc_data(self, pc: PC) -> dict:
        """
        Извлечь данные из объекта PC в словарь
        
        Args:
            pc: Объект ПК
            
        Returns:
            Словарь с данными ПК
        """
        return {
            'pc_id': pc.pc_id,
            'hostname': pc.hostname,
            'location': pc.location,
            'building': pc.building,
            'floor': pc.floor,
            'status': pc.status
        }
    
    def _extract_event_data(self, event: ChangeEvent) -> dict:
        """
        Извлечь данные из объекта Event в словарь
        
        Args:
            event: Объект события
            
        Returns:
            Словарь с данными события
        """
        return {
            'id': event.id if hasattr(event, 'id') else None,
            'pc_id': event.pc_id,
            'component_type': event.component_type,
            'event_type': event.event_type,
            'timestamp': event.timestamp,
            'details': event.details,
            'old_value': event.get_old_value(),
            'new_value': event.get_new_value()
        }
    
    def _send_notifications_after_commit(
        self,
        pc_data: dict,
        events_data: List[dict],
        notification_service: NotificationService
    ) -> None:
        """
        Отправить уведомления после коммита транзакции
        
        Args:
            pc_data: Словарь с данными ПК
            events_data: Список словарей с данными событий
            notification_service: Сервис уведомлений
        """
        # Для отправки уведомлений нужно загрузить объекты из БД
        # Используем новую сессию для этого
        from infrastructure.database.session import SessionLocal
        from infrastructure.database.models import PC, ChangeEvent
        
        db = SessionLocal()
        try:
            # Загружаем ПК по ID
            pc = db.query(PC).filter(PC.pc_id == pc_data['pc_id']).first()
            if not pc:
                self.logger.error(f"ПК {pc_data['pc_id']} не найден для отправки уведомления")
                return
            
            # Загружаем события для отправки уведомлений
            # Используем подход с загрузкой последних событий для ПК
            from datetime import timedelta
            import time
            
            if events_data:
                # Получаем самый ранний timestamp из событий
                timestamps = [e.get('timestamp') for e in events_data if e.get('timestamp')]
                if timestamps:
                    min_timestamp = min(timestamps)
                    # Загружаем все события для этого ПК за последние 10 секунд
                    # Используем диапазон вместо точного совпадения, так как timestamp может немного отличаться
                    search_from = min_timestamp - timedelta(seconds=10)
                    search_to = min_timestamp + timedelta(seconds=2)
                    
                    # Из-за изоляции транзакций SQLite в WAL режиме, поиск по ID сразу после коммита
                    # может не работать. Используем более надежный подход - поиск по timestamp и другим критериям
                    time.sleep(0.2)  # Небольшая задержка для WAL режима SQLite
                    
                    # Загружаем недавние события для этого ПК по времени
                    recent_events = db.query(ChangeEvent).filter(
                        ChangeEvent.pc_id == pc_data['pc_id'],
                        ChangeEvent.timestamp >= search_from,
                        ChangeEvent.timestamp <= search_to
                    ).order_by(ChangeEvent.timestamp.desc(), ChangeEvent.id.desc()).all()
                    
                    # Создаем индекс для быстрого поиска событий по комбинации критериев
                    # Используем (component_type, event_type, timestamp) как ключ для точного поиска
                    event_map = {}
                    for evt in recent_events:
                        # Используем timestamp с точностью до микросекунды для точного совпадения
                        event_timestamp_str = evt.timestamp.isoformat() if evt.timestamp else None
                        key = (evt.component_type, evt.event_type, event_timestamp_str)
                        event_map[key] = evt
                    
                    # Логируем информацию о загруженных событиях
                    self.logger.info(
                        f"Загружено {len(recent_events)} недавних событий для ПК {pc_data['pc_id']} "
                        f"в диапазоне {search_from} - {search_to}. "
                        f"Ключи в event_map: {[(k[0], k[1], k[2][:19] if k[2] else None) for k in list(event_map.keys())[:5]]}"
                    )
                    
                    # Находим и отправляем уведомления для каждого события
                    for event_data in events_data:
                        event = None
                        event_id = event_data.get('id')
                        component_type = event_data.get('component_type')
                        event_type = event_data.get('event_type')
                        event_timestamp = event_data.get('timestamp')
                        
                        # Ищем событие по точному совпадению component_type, event_type и timestamp
                        if component_type and event_type and event_timestamp:
                            # Форматируем timestamp в строку для сравнения
                            if isinstance(event_timestamp, datetime):
                                event_timestamp_str = event_timestamp.isoformat()
                            else:
                                event_timestamp_str = str(event_timestamp)
                            
                            key = (component_type, event_type, event_timestamp_str)
                            event = event_map.get(key)
                            
                            if event:
                                self.logger.info(f"Событие найдено по ключу {key}, ID={event.id}")
                            else:
                                self.logger.warning(
                                    f"Точное совпадение не найдено для ключа {key}. "
                                    f"Доступные ключи: {[(k[0], k[1], k[2][:19] if k[2] else None) for k in list(event_map.keys())[:10]]}"
                                )
                                # Если точное совпадение не найдено, пробуем найти по component_type и event_type
                                # (берем самое последнее событие этого типа)
                                for (comp, evt_type, ts), evt in event_map.items():
                                    if comp == component_type and evt_type == event_type:
                                        event = evt
                                        self.logger.info(
                                            f"Событие найдено по типу {component_type}/{event_type}, "
                                            f"ID={event.id} (timestamp не точно совпадает)"
                                        )
                                        break
                        
                        if event:
                            try:
                                notification_service.send_alert(pc, event)
                                self.logger.debug(f"Уведомление отправлено для события {event.id}")
                            except Exception as notif_err:
                                # Логируем ошибку, но НЕ прерываем выполнение
                                # События уже сохранены в БД, уведомления - вторичная функция
                                self.logger.error(
                                    f"Ошибка отправки уведомления для события {event_id or 'unknown'}: {notif_err}",
                                    exc_info=True
                                )
                        else:
                            self.logger.warning(
                                f"Событие не найдено для отправки уведомления "
                                f"(pc_id={event_data.get('pc_id')}, component={component_type}, "
                                f"type={event_type}, id={event_id}, timestamp={event_data.get('timestamp')})"
                            )
        finally:
            db.close()
