"""
Сервис для работы с событиями изменений
Бизнес-логика создания и обработки событий
"""
import logging
from typing import List

from common.models import ChangeEvent as DomainChangeEvent
from infrastructure.database.models import ChangeEvent as DBChangeEvent
from infrastructure.database.repositories.event_repository import EventRepository


class EventService:
    """Сервис для работы с событиями изменений"""
    
    def __init__(self, event_repository: EventRepository):
        self.event_repository = event_repository
        self.logger = logging.getLogger(__name__)
    
    def create_events_from_domain(self, domain_events: List[DomainChangeEvent]) -> List[DBChangeEvent]:
        """
        Создать события БД из domain событий
        
        Args:
            domain_events: Список domain событий
            
        Returns:
            Список событий БД
        """
        db_events = []
        
        for domain_event in domain_events:
            db_event = DBChangeEvent(
                pc_id=domain_event.pc_id,
                component_type=domain_event.component_type,
                event_type=domain_event.event_type,
                timestamp=domain_event.timestamp,
                details=domain_event.details
            )
            db_event.set_old_value(domain_event.old_value)
            db_event.set_new_value(domain_event.new_value)
            
            self.event_repository.create(db_event)
            db_events.append(db_event)
        
        return db_events









