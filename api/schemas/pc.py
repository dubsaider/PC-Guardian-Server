"""
Pydantic схемы для ПК
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class PCBase(BaseModel):
    """Базовая схема ПК"""
    pc_id: str
    hostname: str
    status: str
    registered_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    location: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None


class PCResponse(PCBase):
    """Схема ответа для ПК"""
    id: int
    agent_version: Optional[str] = None
    ip_address: Optional[str] = None
    ip_addresses: Optional[list[str]] = None
    
    class Config:
        from_attributes = True


class PCDetailResponse(PCResponse):
    """Схема детального ответа для ПК с конфигурациями"""
    baseline_config: Optional[Dict[str, Any]] = None
    current_config: Optional[Dict[str, Any]] = None


class PCListResponse(BaseModel):
    """Схема ответа для списка ПК"""
    total: int
    items: list[PCResponse]


class SetBaselineResponse(BaseModel):
    """Схема ответа для установки эталонной конфигурации"""
    message: str
    pc_id: str



