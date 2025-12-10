"""
Pydantic схемы для правил уведомлений
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AlertRuleFilterSchema(BaseModel):
    """Схема фильтра правила уведомлений"""
    buildings: Optional[List[str]] = Field(None, description="Список корпусов")
    floors: Optional[List[str]] = Field(None, description="Список этажей")
    locations: Optional[List[str]] = Field(None, description="Список локаций")
    component_types: Optional[List[str]] = Field(None, description="Типы компонентов")
    event_types: Optional[List[str]] = Field(None, description="Типы событий")
    exclude_component_types: Optional[List[str]] = Field(None, description="Исключаемые типы компонентов")


class AlertRuleBase(BaseModel):
    """Базовая схема правила уведомлений"""
    name: str = Field(..., description="Название правила")
    enabled: bool = Field(True, description="Включено ли правило")
    channels: List[str] = Field(["email"], description="Каналы уведомлений: email, telegram")
    filters: Optional[AlertRuleFilterSchema] = Field(None, description="Фильтры правила")
    recipients: List[str] = Field(..., description="Список получателей (email или telegram chat_id)")


class AlertRuleCreate(AlertRuleBase):
    """Схема создания правила уведомлений"""
    pass


class AlertRuleUpdate(BaseModel):
    """Схема обновления правила уведомлений"""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    channels: Optional[List[str]] = None
    filters: Optional[AlertRuleFilterSchema] = None
    recipients: Optional[List[str]] = None


class AlertRuleResponse(AlertRuleBase):
    """Схема ответа для правила уведомлений"""
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AlertRuleListResponse(BaseModel):
    """Схема списка правил уведомлений"""
    total: int
    items: List[AlertRuleResponse]

