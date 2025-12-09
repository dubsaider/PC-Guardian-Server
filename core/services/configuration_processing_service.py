"""
Сервис для обработки конфигураций ПК
Главный сервис, объединяющий всю бизнес-логику обработки конфигураций
"""
import logging
from datetime import datetime

from common.models import PCConfiguration
from infrastructure.database.session import SessionLocal
from infrastructure.database.repositories.pc_repository import PCRepository
from infrastructure.database.repositories.config_repository import ConfigRepository
from infrastructure.database.repositories.current_config_repository import CurrentConfigRepository
from infrastructure.database.repositories.event_repository import EventRepository
from infrastructure.database.models import PCConfiguration as DBPCConfiguration
from infrastructure.messaging.notification_service import NotificationService

from core.services.pc_service import PCService
from core.services.config_service import ConfigService
from core.services.event_service import EventService
from core.services.comparison_service import ComparisonService
from common.location_parser import update_pc_location


class ConfigurationProcessingService:
    """
    Сервис для обработки входящих конфигураций ПК
    Объединяет всю бизнес-логику: регистрацию ПК, сравнение конфигураций, создание событий
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_service = ConfigService()
        self.comparison_service = ComparisonService()
        self.notification_service = NotificationService()
    
    def process_configuration(self, config: PCConfiguration) -> None:
        """
        Обработать полученную конфигурацию ПК
        
        Полная бизнес-логика:
        1. Найти или создать ПК
        2. Создать текущую конфигурацию
        3. Сравнить с эталонной (если есть)
        4. Создать события изменений
        5. Отправить уведомления
        
        Args:
            config: Domain модель конфигурации ПК
        """
        db = SessionLocal()
        try:
            # Инициализируем репозитории и сервисы
            pc_repo = PCRepository(db)
            config_repo = ConfigRepository(db)
            current_config_repo = CurrentConfigRepository(db)
            event_repo = EventRepository(db)
            
            pc_service = PCService(pc_repo)
            
            last_seen_time = config.timestamp if config.timestamp else datetime.utcnow()
            
            # Логирование входящей конфигурации
            self.logger.info(
                f"Processing config for {config.pc_id}: "
                f"agent_version={config.agent_version}, "
                f"network_adapters_count={len(config.network_adapters) if config.network_adapters else 0}"
            )
            
            # Находим или создаем ПК
            pc = pc_service.find_or_create_pc(
                pc_id=config.pc_id,
                hostname=config.hostname,
                last_seen=last_seen_time
            )
            
            # Обновляем локацию, если она пришла от агента
            if config.location:
                update_pc_location(pc, config.location)
                pc_repo.update(pc)
            
            # Получаем эталонную конфигурацию
            baseline = config_repo.find_baseline(pc.pc_id)
            
            if not baseline:
                # Нет эталонной конфигурации - создаем её и текущую (новый ПК или первый раз)
                baseline_db = self.config_service.create_db_configuration(
                    pc.pc_id, config, is_baseline=True
                )
                config_repo.create(baseline_db)
                
                current_db = self.config_service.create_db_configuration(
                    pc.pc_id, config, is_baseline=False
                )
                config_repo.create(current_db)
                
                # Сохраняем текущее состояние
                current_config = self.config_service.create_current_configuration(
                    pc.pc_id, config
                )
                current_config_repo.create_or_update(current_config)
                
                pc_service.update_status(pc, 'normal')
                self.logger.info(f"Создана эталонная конфигурация для ПК: {config.pc_id}")
            else:
                # Есть эталонная - сравниваем с текущей
                pc_service.update_last_seen(pc, last_seen_time)
                
                # Создаем текущую конфигурацию
                current_db = self.config_service.create_db_configuration(
                    pc.pc_id, config, is_baseline=False
                )
                
                # Логирование созданной конфигурации перед сохранением
                self.logger.info(
                    f"Created current config for {pc.pc_id}: "
                    f"agent_version={current_db.agent_version}, "
                    f"has_network_adapters={bool(current_db.network_adapters)}, "
                    f"timestamp={current_db.timestamp}"
                )
                
                # Сравниваем конфигурации (получаем domain события)
                domain_events = self.comparison_service.compare_configurations(baseline, current_db)
                
                if domain_events:
                    # Есть изменения
                    pc_service.update_status(pc, 'changed')
                    
                    # Создаем события БД
                    event_service = EventService(event_repo)
                    db_events = event_service.create_events_from_domain(domain_events)
                    
                    # Отправляем уведомления
                    for domain_event, db_event in zip(domain_events, db_events):
                        self.notification_service.send_alert(pc, db_event)
                    
                    self.logger.warning(
                        f"Обнаружены изменения на ПК {config.pc_id}: {len(domain_events)} событий"
                    )
                else:
                    # Нет изменений
                    pc_service.update_status(pc, 'normal')
                
                # Сохраняем текущую конфигурацию в историю
                config_repo.create(current_db)
                
                # Обновляем текущее состояние
                current_config = self.config_service.create_current_configuration(
                    pc.pc_id, config
                )
                current_config_repo.create_or_update(current_config)
                
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки конфигурации: {e}", exc_info=True)
            db.rollback()
            raise
        finally:
            db.close()
