"""
Pydantic схемы для статистики
"""
from pydantic import BaseModel


class StatsResponse(BaseModel):
    """Схема ответа для статистики"""
    total_pcs: int
    normal_pcs: int
    changed_pcs: int
    offline_pcs: int
    recent_events: int




