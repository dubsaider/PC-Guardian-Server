"""
Веб-маршруты для страницы правил уведомлений
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from infrastructure.database.models import User
from api.dependencies import get_current_user, get_user_from_token
from infrastructure.database.session import get_db
from web.dependencies import get_templates
from jinja2 import Environment
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/alert-rules", response_class=HTMLResponse)
async def alert_rules_page(
    request: Request,
    db: Session = Depends(get_db),
    templates: Environment = Depends(get_templates)
):
    """Страница управления правилами уведомлений"""
    # Проверяем авторизацию вручную для веб-роутов
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/login", status_code=303)
    
    user = get_user_from_token(session_token, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    template = templates.get_template("alert_rules.html")
    return HTMLResponse(template.render(request=request, user=user))

