"""
Pydantic схемы для работы с локациями
"""
from typing import Optional, List
from pydantic import BaseModel


class UpdateLocationRequest(BaseModel):
    """Схема для обновления локации одного ПК"""
    location: Optional[str] = None


class BulkUpdateLocationRequest(BaseModel):
    """Схема для массового обновления локаций"""
    updates: List[dict]  # Список {pc_id: str, location: str}


class BulkUpdateLocationResponse(BaseModel):
    """Схема ответа для массового обновления"""
    updated: int
    failed: int
    errors: List[str] = []


