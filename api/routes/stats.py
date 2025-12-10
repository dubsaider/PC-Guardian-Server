"""
API маршруты для статистики
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from infrastructure.database.session import get_db
from infrastructure.database.models import User, PC
from infrastructure.database.repositories.pc_repository import PCRepository
from infrastructure.database.repositories.event_repository import EventRepository
from api.dependencies import get_current_user
from api.schemas.stats import StatsResponse

router = APIRouter(prefix="/api/stats", tags=["Stats"])


def get_pc_repository(db: Session = Depends(get_db)) -> PCRepository:
    """Dependency для получения репозитория ПК"""
    return PCRepository(db)


def get_event_repository(db: Session = Depends(get_db)) -> EventRepository:
    """Dependency для получения репозитория событий"""
    return EventRepository(db)


@router.get("", response_model=StatsResponse)
async def get_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository),
    event_repo: EventRepository = Depends(get_event_repository)
):
    """Получить статистику"""
    # Обновляем статус offline перед подсчетом статистики
    pc_repo.update_offline_status(offline_threshold_minutes=10)
    
    total_pcs = pc_repo.count_all()
    normal_pcs = pc_repo.count_all(status='normal')
    changed_pcs = pc_repo.count_all(status='changed')
    
    # Подсчитываем offline ПК (используем тот же порог - 10 минут)
    offline_threshold = datetime.utcnow() - timedelta(minutes=10)
    offline_pcs = db.query(PC).filter(
        PC.last_seen.isnot(None),
        PC.last_seen < offline_threshold
    ).count()
    
    recent_events = event_repo.count_recent(days=7)
    
    return StatsResponse(
        total_pcs=total_pcs,
        normal_pcs=normal_pcs,
        changed_pcs=changed_pcs,
        offline_pcs=offline_pcs,
        recent_events=recent_events
    )




