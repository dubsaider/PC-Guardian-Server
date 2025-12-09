"""
API маршруты для работы с событиями
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from infrastructure.database.session import get_db
from infrastructure.database.models import User
from infrastructure.database.repositories.event_repository import EventRepository
from api.dependencies import get_current_user
from api.schemas.event import EventListResponse

router = APIRouter(prefix="/api/events", tags=["Events"])


def get_event_repository(db: Session = Depends(get_db)) -> EventRepository:
    """Dependency для получения репозитория событий"""
    return EventRepository(db)


@router.get("", response_model=EventListResponse)
async def get_events(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    pc_id: Optional[str] = None,
    component_type: Optional[str] = None,
    event_type: Optional[str] = None,
    building: Optional[str] = None,
    floor: Optional[str] = None,
    location: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: str = 'desc',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event_repo: EventRepository = Depends(get_event_repository)
):
    """Получить все события с фильтрацией и сортировкой"""
    # Парсим даты
    date_from_dt = None
    date_to_dt = None
    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        except:
            pass
    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        except:
            pass
    
    events = event_repo.find_all(
        skip=skip,
        limit=limit,
        pc_id=pc_id,
        component_type=component_type,
        event_type=event_type,
        building=building,
        floor=floor,
        location=location,
        date_from=date_from_dt,
        date_to=date_to_dt,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )
    total = event_repo.count_all(
        pc_id=pc_id,
        component_type=component_type,
        event_type=event_type,
        building=building,
        floor=floor,
        location=location,
        date_from=date_from_dt,
        date_to=date_to_dt,
        search=search
    )
    
    return EventListResponse(
        total=total,
        items=[event.to_dict() for event in events]
    )



