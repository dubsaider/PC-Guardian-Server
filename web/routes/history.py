"""
Web роутеры для страницы истории изменений конфигурации ПК
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from infrastructure.database.session import get_db
from infrastructure.database.repositories.pc_repository import PCRepository
from api.dependencies import get_current_user
from infrastructure.database.models import User
from web.dependencies import get_templates
from jinja2 import Environment

router = APIRouter()


def get_pc_repository(db: Session = Depends(get_db)) -> PCRepository:
    """Dependency для получения репозитория ПК"""
    return PCRepository(db)


@router.get("/pc/{pc_id}/history", response_class=HTMLResponse)
async def pc_history_page(
    pc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    templates: Environment = Depends(get_templates),
    pc_repo: PCRepository = Depends(get_pc_repository)
):
    """Страница истории изменений конфигурации ПК"""
    # Проверяем, что ПК существует
    pc = pc_repo.find_by_id(pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    template = templates.get_template("pc_history.html")
    return HTMLResponse(template.render(request=request, user=current_user, pc=pc))

