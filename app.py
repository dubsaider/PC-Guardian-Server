"""
FastAPI приложение для PC-Guardian Server
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta

from database import get_db, Base, engine, PC, PCConfiguration, ChangeEvent, User
from kafka_consumer import PCGuardianConsumer
from common.kafka_config import KafkaConfig
from auth import get_current_user, create_user, verify_password, get_password_hash

# Создаем таблицы БД
Base.metadata.create_all(bind=engine)

# Инициализация Kafka Consumer
kafka_config = KafkaConfig()
consumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global consumer
    # Запуск при старте
    consumer = PCGuardianConsumer(kafka_config)
    consumer.start()
    yield
    # Остановка при завершении
    if consumer:
        consumer.stop()


app = FastAPI(
    title="PC-Guardian Server",
    description="Система мониторинга комплектующих ПК",
    version="1.0.0",
    lifespan=lifespan
)

# Настройка шаблонов
templates = Environment(loader=FileSystemLoader("templates"))

# Статические файлы
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ==================== API Endpoints ====================

@app.get("/api/pcs", response_class=JSONResponse)
async def get_pcs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список ПК"""
    query = db.query(PC)
    
    if status:
        query = query.filter(PC.status == status)
    
    pcs = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "total": total,
        "items": [pc.to_dict() for pc in pcs]
    }


@app.get("/api/pcs/{pc_id}", response_class=JSONResponse)
async def get_pc(
    pc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить информацию о ПК"""
    pc = db.query(PC).filter(PC.pc_id == pc_id).first()
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    # Получаем эталонную конфигурацию
    baseline = db.query(PCConfiguration).filter_by(
        pc_id=pc_id,
        is_baseline=True
    ).first()
    
    # Получаем последнюю конфигурацию
    latest = db.query(PCConfiguration).filter_by(
        pc_id=pc_id,
        is_baseline=False
    ).order_by(PCConfiguration.timestamp.desc()).first()
    
    result = pc.to_dict()
    result['baseline_config'] = baseline.to_dict() if baseline else None
    result['latest_config'] = latest.to_dict() if latest else None
    
    return result


@app.get("/api/pcs/{pc_id}/events", response_class=JSONResponse)
async def get_pc_events(
    pc_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить события для ПК"""
    events = db.query(ChangeEvent).filter(
        ChangeEvent.pc_id == pc_id
    ).order_by(ChangeEvent.timestamp.desc()).offset(skip).limit(limit).all()
    
    total = db.query(ChangeEvent).filter(ChangeEvent.pc_id == pc_id).count()
    
    return {
        "total": total,
        "items": [event.to_dict() for event in events]
    }


@app.post("/api/pcs/{pc_id}/baseline", response_class=JSONResponse)
async def set_baseline(
    pc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Установить текущую конфигурацию как эталонную"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pc = db.query(PC).filter(PC.pc_id == pc_id).first()
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    # Получаем последнюю конфигурацию
    latest = db.query(PCConfiguration).filter_by(
        pc_id=pc_id,
        is_baseline=False
    ).order_by(PCConfiguration.timestamp.desc()).first()
    
    if not latest:
        raise HTTPException(status_code=404, detail="No configuration found")
    
    # Снимаем флаг эталонной со всех старых
    db.query(PCConfiguration).filter_by(
        pc_id=pc_id,
        is_baseline=True
    ).update({"is_baseline": False})
    
    # Устанавливаем новую эталонную
    latest.is_baseline = True
    pc.status = 'normal'
    
    db.commit()
    
    return {"message": "Baseline configuration updated", "pc_id": pc_id}


@app.get("/api/events", response_class=JSONResponse)
async def get_events(
    skip: int = 0,
    limit: int = 100,
    pc_id: Optional[str] = None,
    component_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить все события"""
    query = db.query(ChangeEvent)
    
    if pc_id:
        query = query.filter(ChangeEvent.pc_id == pc_id)
    if component_type:
        query = query.filter(ChangeEvent.component_type == component_type)
    
    events = query.order_by(ChangeEvent.timestamp.desc()).offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "total": total,
        "items": [event.to_dict() for event in events]
    }


@app.get("/api/stats", response_class=JSONResponse)
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить статистику"""
    total_pcs = db.query(PC).count()
    normal_pcs = db.query(PC).filter(PC.status == 'normal').count()
    changed_pcs = db.query(PC).filter(PC.status == 'changed').count()
    offline_pcs = db.query(PC).filter(
        PC.last_seen < datetime.utcnow() - timedelta(hours=24)
    ).count()
    
    recent_events = db.query(ChangeEvent).filter(
        ChangeEvent.timestamp >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    return {
        "total_pcs": total_pcs,
        "normal_pcs": normal_pcs,
        "changed_pcs": changed_pcs,
        "offline_pcs": offline_pcs,
        "recent_events": recent_events
    }


# ==================== Web Interface ====================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: User = Depends(get_current_user)):
    """Главная страница - дашборд"""
    template = templates.get_template("dashboard.html")
    return HTMLResponse(template.render(request=request, user=current_user))


@app.get("/pc/{pc_id}", response_class=HTMLResponse)
async def pc_detail(
    pc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Страница детального просмотра ПК"""
    pc = db.query(PC).filter(PC.pc_id == pc_id).first()
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    template = templates.get_template("pc_detail.html")
    return HTMLResponse(template.render(request=request, user=current_user, pc=pc))


@app.get("/events", response_class=HTMLResponse)
async def events_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Страница журнала событий"""
    template = templates.get_template("events.html")
    return HTMLResponse(template.render(request=request, user=current_user))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    template = templates.get_template("login.html")
    return HTMLResponse(template.render(request=request))


@app.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Обработка входа"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # В реальном приложении здесь должна быть установка сессии/JWT токена
    return {"message": "Login successful", "user": user.username}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

