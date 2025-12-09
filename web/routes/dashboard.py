"""
Веб-маршруты для дашборда
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from infrastructure.database.models import User
from infrastructure.database.session import get_db
from api.dependencies import get_current_user
from web.dependencies import get_templates
from jinja2 import Environment

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    templates: Environment = Depends(get_templates)
):
    """Главная страница - дашборд"""
    template = templates.get_template("dashboard.html")
    return HTMLResponse(template.render(request=request, user=current_user))



