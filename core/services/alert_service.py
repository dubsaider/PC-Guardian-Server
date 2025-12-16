"""
Сервис для работы с правилами уведомлений
Бизнес-логика проверки правил и отправки уведомлений
"""
import logging
from typing import List, Optional
from datetime import datetime

from infrastructure.database.models import PC, ChangeEvent, AlertRule as DBAlertRule
from infrastructure.database.repositories.alert_rule_repository import AlertRuleRepository
from core.domain.alert_rule import AlertRule, AlertRuleFilter


class AlertService:
    """Сервис для работы с правилами уведомлений"""
    
    def __init__(self, alert_rule_repository: AlertRuleRepository):
        self.alert_rule_repository = alert_rule_repository
        self.logger = logging.getLogger(__name__)
    
    def get_matching_rules(
        self,
        pc: PC,
        event: ChangeEvent,
        user_id: Optional[int] = None
    ) -> List[DBAlertRule]:
        """
        Найти правила, которые соответствуют событию
        
        Args:
            pc: Объект ПК
            event: Событие изменения
            user_id: ID пользователя (для фильтрации правил)
            
        Returns:
            Список правил, которые соответствуют событию
        """
        # Получаем все активные правила (глобальные + пользовательские)
        all_rules = self.alert_rule_repository.find_all(
            user_id=user_id,
            enabled_only=True
        )
        
        matching_rules = []
        
        for db_rule in all_rules:
            # Преобразуем в domain модель
            domain_rule = self._db_to_domain(db_rule)
            
            # Проверяем соответствие
            if domain_rule.matches(
                building=pc.building,
                floor=pc.floor,
                location=pc.location,
                component_type=event.component_type,
                event_type=event.event_type
            ):
                matching_rules.append(db_rule)
        
        return matching_rules
    
    def _db_to_domain(self, db_rule: DBAlertRule) -> AlertRule:
        """Преобразовать DB модель в domain модель"""
        filters = None
        if db_rule.get_filters():
            filters = AlertRuleFilter.from_dict(db_rule.get_filters())
        
        return AlertRule(
            id=db_rule.id,
            name=db_rule.name,
            user_id=db_rule.user_id,
            enabled=db_rule.enabled,
            channels=db_rule.get_channels(),
            filters=filters,
            recipients=db_rule.get_recipients(),
            email_grouping_enabled=db_rule.email_grouping_enabled,
            created_at=db_rule.created_at,
            updated_at=db_rule.updated_at
        )
    
    def _domain_to_db(self, domain_rule: AlertRule) -> DBAlertRule:
        """Преобразовать domain модель в DB модель"""
        db_rule = DBAlertRule(
            name=domain_rule.name,
            user_id=domain_rule.user_id,
            enabled=domain_rule.enabled,
            email_grouping_enabled=domain_rule.email_grouping_enabled
        )
        
        db_rule.set_channels(domain_rule.channels)
        db_rule.set_recipients(domain_rule.recipients)
        
        if domain_rule.filters:
            db_rule.set_filters(domain_rule.filters.to_dict())
        
        return db_rule





