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
from infrastructure.database.repositories.alert_rule_repository import AlertRuleRepository
from infrastructure.database.models import PCConfiguration as DBPCConfiguration
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
            alert_rule_repo = AlertRuleRepository(db)
            
            pc_service = PCService(pc_repo)
            alert_service = AlertService(alert_rule_repo)
            notification_service = NotificationService(alert_service)
            
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
                # Есть эталонная - сравниваем с текущим состоянием
                pc_service.update_last_seen(pc, last_seen_time)
                
                # Получаем текущее состояние (если есть)
                current_state = current_config_repo.find_by_pc_id(pc.pc_id)
                
                # Создаем объект новой конфигурации для сравнения
                new_config_db = self.config_service.create_db_configuration(
                    pc.pc_id, config, is_baseline=False
                )
                
                # Сравниваем с текущим состоянием (если есть), иначе с эталонной
                if current_state:
                    # Преобразуем PCCurrentConfiguration в DBPCConfiguration для сравнения
                    from infrastructure.database.models import PCConfiguration as DBPCConfiguration
                    current_state_db = DBPCConfiguration.from_current_configuration(current_state)
                    # Сравниваем новую конфигурацию с текущим состоянием
                    domain_events = self.comparison_service.compare_configurations(current_state_db, new_config_db)
                else:
                    # Нет текущего состояния - сравниваем с эталонной
                    domain_events = self.comparison_service.compare_configurations(baseline, new_config_db)
                
                if domain_events:
                    # Есть изменения - сохраняем их
                    pc_service.update_status(pc, 'changed')
                    
                    # Создаем события БД
                    event_service = EventService(event_repo)
                    db_events = event_service.create_events_from_domain(domain_events)
                    
                    # Отправляем уведомления
                    for domain_event, db_event in zip(domain_events, db_events):
                        notification_service.send_alert(pc, db_event)
                    
                    self.logger.warning(
                        f"Обнаружены изменения на ПК {config.pc_id}: {len(domain_events)} событий"
                    )
                else:
                    # Нет изменений
                    pc_service.update_status(pc, 'normal')
                
                # НЕ сохраняем конфигурацию в историю - храним только эталонную
                # Обновляем только текущее состояние
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
