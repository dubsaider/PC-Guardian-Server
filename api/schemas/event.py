"""
Pydantic схемы для событий
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class EventBase(BaseModel):
    """Базовая схема события"""
    pc_id: str
    component_type: str
    event_type: str
    timestamp: datetime
    details: Optional[str] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None


class EventResponse(EventBase):
    """Схема ответа для события"""
    id: int
    notified: bool
    notified_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Схема ответа для списка событий"""
    total: int
    items: list[EventResponse]



