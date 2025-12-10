"""
Репозиторий для работы с правилами уведомлений
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from infrastructure.database.models import AlertRule as DBAlertRule


class AlertRuleRepository:
    """Репозиторий для работы с правилами уведомлений"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_by_id(self, rule_id: int) -> Optional[DBAlertRule]:
        """Найти правило по ID"""
        return self.db.query(DBAlertRule).filter(DBAlertRule.id == rule_id).first()
    
    def find_all(
        self,
        user_id: Optional[int] = None,
        enabled_only: bool = False
    ) -> List[DBAlertRule]:
        """
        Найти все правила
        
        Args:
            user_id: Фильтр по пользователю (None = все, включая глобальные)
            enabled_only: Только включенные правила
        """
        query = self.db.query(DBAlertRule)
        
        if user_id is not None:
            # Правила пользователя или глобальные (user_id is None)
            query = query.filter(
                (DBAlertRule.user_id == user_id) | (DBAlertRule.user_id.is_(None))
            )
        
        if enabled_only:
            query = query.filter(DBAlertRule.enabled == True)
        
        return query.order_by(DBAlertRule.created_at.desc()).all()
    
    def find_by_user(self, user_id: int) -> List[DBAlertRule]:
        """Найти правила пользователя"""
        return self.db.query(DBAlertRule).filter(
            DBAlertRule.user_id == user_id
        ).order_by(DBAlertRule.created_at.desc()).all()
    
    def find_global(self, enabled_only: bool = False) -> List[DBAlertRule]:
        """Найти глобальные правила (без владельца)"""
        query = self.db.query(DBAlertRule).filter(DBAlertRule.user_id.is_(None))
        
        if enabled_only:
            query = query.filter(DBAlertRule.enabled == True)
        
        return query.order_by(DBAlertRule.created_at.desc()).all()
    
    def create(self, rule: DBAlertRule) -> DBAlertRule:
        """Создать новое правило"""
        rule.updated_at = datetime.utcnow()
        self.db.add(rule)
        self.db.flush()
        return rule
    
    def update(self, rule: DBAlertRule) -> DBAlertRule:
        """Обновить правило"""
        rule.updated_at = datetime.utcnow()
        self.db.flush()
        return rule
    
    def delete(self, rule: DBAlertRule) -> None:
        """Удалить правило"""
        self.db.delete(rule)
        self.db.flush()

