"""
Веб-маршруты для детального просмотра ПК
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from infrastructure.database.models import User, PC
from infrastructure.database.session import get_db
from infrastructure.database.repositories.pc_repository import PCRepository
from api.dependencies import get_current_user
from web.dependencies import get_templates
from jinja2 import Environment

router = APIRouter()


def get_pc_repository(db: Session = Depends(get_db)) -> PCRepository:
    """Dependency для получения репозитория ПК"""
    return PCRepository(db)


@router.get("/pc/{pc_id}", response_class=HTMLResponse)
async def pc_detail(
    pc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    templates: Environment = Depends(get_templates),
    pc_repo: PCRepository = Depends(get_pc_repository)
):
    """Страница детального просмотра ПК"""
    # Обновляем статус offline перед получением информации
    pc_repo.update_offline_status(offline_threshold_minutes=10)
    
    pc = pc_repo.find_by_id(pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    template = templates.get_template("pc_detail.html")
    return HTMLResponse(template.render(request=request, user=current_user, pc=pc))




