"""
Веб-маршруты для страницы событий
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from infrastructure.database.models import User
from api.dependencies import get_current_user
from web.dependencies import get_templates
from jinja2 import Environment

router = APIRouter()


@router.get("/events", response_class=HTMLResponse)
async def events_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    templates: Environment = Depends(get_templates)
):
    """Страница журнала событий"""
    template = templates.get_template("events.html")
    return HTMLResponse(template.render(request=request, user=current_user))



