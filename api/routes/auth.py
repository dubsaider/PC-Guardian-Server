"""
Маршруты аутентификации
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from infrastructure.database.session import get_db
from infrastructure.database.models import User
from api.dependencies import (
    get_user_from_token,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request, 
    db: Session = Depends(get_db)
):
    """Страница входа"""
    # Проверяем, есть ли уже активная сессия
    session_token = request.cookies.get("session_token")
    if session_token:
        user = get_user_from_token(session_token, db)
        if user:
            return RedirectResponse(url="/", status_code=303)
    
    # Импортируем шаблон здесь, чтобы избежать циклических зависимостей
    from jinja2 import Environment, FileSystemLoader
    templates = Environment(loader=FileSystemLoader("templates"))
    template = templates.get_template("login.html")
    return HTMLResponse(template.render(request=request))


@router.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Обработка входа"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    
    # Создаем JWT токен
    access_token = create_access_token(data={"sub": user.username})
    
    # Создаем ответ с редиректом
    response = RedirectResponse(url="/", status_code=303)
    # Устанавливаем cookie с токеном
    response.set_cookie(
        key="session_token",
        value=access_token,
        max_age=24 * 60 * 60,  # 24 часа
        httponly=True,
        samesite="lax"
    )
    
    return response


@router.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_token")
    return response



