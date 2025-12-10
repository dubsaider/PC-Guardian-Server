"""
API маршруты для управления правилами уведомлений
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from infrastructure.database.session import get_db
from infrastructure.database.repositories.alert_rule_repository import AlertRuleRepository
from infrastructure.database.models import AlertRule as DBAlertRule, User
from api.dependencies import get_current_user
from api.schemas.alert_rule import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertRuleListResponse,
    AlertRuleFilterSchema
)
from core.domain.alert_rule import AlertRule, AlertRuleFilter
from core.services.alert_service import AlertService

router = APIRouter(prefix="/api/alert-rules", tags=["alert-rules"])


def get_alert_rule_repository(db: Session = Depends(get_db)) -> AlertRuleRepository:
    """Получить репозиторий правил уведомлений"""
    return AlertRuleRepository(db)


def get_alert_service(
    alert_rule_repo: AlertRuleRepository = Depends(get_alert_rule_repository)
) -> AlertService:
    """Получить сервис правил уведомлений"""
    return AlertService(alert_rule_repo)


def _domain_to_db(domain_rule: AlertRule) -> DBAlertRule:
    """Преобразовать domain модель в DB модель"""
    db_rule = DBAlertRule(
        name=domain_rule.name,
        user_id=domain_rule.user_id,
        enabled=domain_rule.enabled
    )
    db_rule.set_channels(domain_rule.channels)
    db_rule.set_recipients(domain_rule.recipients)
    
    if domain_rule.filters:
        db_rule.set_filters(domain_rule.filters.to_dict())
    
    return db_rule


def _db_to_response(db_rule: DBAlertRule) -> AlertRuleResponse:
    """Преобразовать DB модель в схему ответа"""
    filters = None
    if db_rule.get_filters():
        filters = AlertRuleFilterSchema(**db_rule.get_filters())
    
    return AlertRuleResponse(
        id=db_rule.id,
        name=db_rule.name,
        user_id=db_rule.user_id,
        enabled=db_rule.enabled,
        channels=db_rule.get_channels(),
        filters=filters,
        recipients=db_rule.get_recipients(),
        created_at=db_rule.created_at,
        updated_at=db_rule.updated_at
    )


@router.get("", response_model=AlertRuleListResponse)
async def get_alert_rules(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    alert_rule_repo: AlertRuleRepository = Depends(get_alert_rule_repository)
):
    """Получить список правил уведомлений (пользовательские + глобальные)"""
    rules = alert_rule_repo.find_all(user_id=current_user.id)
    
    return AlertRuleListResponse(
        total=len(rules),
        items=[_db_to_response(rule) for rule in rules]
    )


@router.get("/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    alert_rule_repo: AlertRuleRepository = Depends(get_alert_rule_repository)
):
    """Получить правило уведомлений по ID"""
    rule = alert_rule_repo.find_by_id(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    
    # Проверяем права доступа (только владелец или админ)
    if rule.user_id and rule.user_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Нет доступа к этому правилу")
    
    return _db_to_response(rule)


@router.post("", response_model=AlertRuleResponse)
async def create_alert_rule(
    rule_data: AlertRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    alert_rule_repo: AlertRuleRepository = Depends(get_alert_rule_repository)
):
    """Создать новое правило уведомлений"""
    # Преобразуем схему в domain модель
    filters = None
    if rule_data.filters:
        filters = AlertRuleFilter.from_dict(rule_data.filters.dict())
    
    domain_rule = AlertRule(
        name=rule_data.name,
        user_id=current_user.id,  # Правило принадлежит текущему пользователю
        enabled=rule_data.enabled,
        channels=rule_data.channels,
        filters=filters,
        recipients=rule_data.recipients
    )
    
    # Преобразуем в DB модель и сохраняем
    db_rule = _domain_to_db(domain_rule)
    alert_rule_repo.create(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    return _db_to_response(db_rule)


@router.patch("/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int,
    rule_data: AlertRuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    alert_rule_repo: AlertRuleRepository = Depends(get_alert_rule_repository)
):
    """Обновить правило уведомлений"""
    rule = alert_rule_repo.find_by_id(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    
    # Проверяем права доступа (только владелец или админ)
    if rule.user_id and rule.user_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Нет доступа к этому правилу")
    
    # Обновляем поля
    if rule_data.name is not None:
        rule.name = rule_data.name
    if rule_data.enabled is not None:
        rule.enabled = rule_data.enabled
    if rule_data.channels is not None:
        rule.set_channels(rule_data.channels)
    if rule_data.recipients is not None:
        rule.set_recipients(rule_data.recipients)
    if rule_data.filters is not None:
        filters = AlertRuleFilter.from_dict(rule_data.filters.dict())
        rule.set_filters(filters.to_dict())
    
    alert_rule_repo.update(rule)
    db.commit()
    db.refresh(rule)
    
    return _db_to_response(rule)


@router.delete("/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    alert_rule_repo: AlertRuleRepository = Depends(get_alert_rule_repository)
):
    """Удалить правило уведомлений"""
    rule = alert_rule_repo.find_by_id(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    
    # Проверяем права доступа (только владелец или админ)
    if rule.user_id and rule.user_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Нет доступа к этому правилу")
    
    alert_rule_repo.delete(rule)
    db.commit()
    
    return {"message": "Правило удалено"}

