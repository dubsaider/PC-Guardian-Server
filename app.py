"""
FastAPI приложение для PC-Guardian Server
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from database import get_db, Base, engine, PC, PCConfiguration, ChangeEvent, User, Room, Camera
from kafka_consumer import PCGuardianConsumer
from common.kafka_config import KafkaConfig
from auth import get_current_user, verify_password, create_access_token
from pydantic import BaseModel as PydanticBaseModel

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

def require_admin(current_user: User = Depends(get_current_user)):
    """Вспомогательная функция для проверки прав администратора"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def update_offline_status(db: Session, offline_threshold_minutes: int = 10):
    """Обновить статус ПК на 'offline' если они не были в сети дольше порога"""
    threshold = datetime.utcnow() - timedelta(minutes=offline_threshold_minutes)
    
    # Находим ПК, которые не были в сети дольше порога
    offline_pcs = db.query(PC).filter(
        PC.last_seen.isnot(None),
        PC.last_seen < threshold,
        PC.status != 'offline'
    ).all()
    
    for pc in offline_pcs:
        pc.status = 'offline'
    
    if offline_pcs:
        db.commit()

@app.get("/api/pcs", response_class=JSONResponse)
async def get_pcs(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список ПК"""
    # Обновляем статус offline перед получением списка
    update_offline_status(db, offline_threshold_minutes=10)
    
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить информацию о ПК"""
    # Обновляем статус offline перед получением информации
    update_offline_status(db, offline_threshold_minutes=10)
    
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
    request: Request,
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
    request: Request,
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
    request: Request,
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить статистику"""
    # Обновляем статус offline перед подсчетом статистики
    update_offline_status(db, offline_threshold_minutes=10)
    
    total_pcs = db.query(PC).count()
    normal_pcs = db.query(PC).filter(PC.status == 'normal').count()
    changed_pcs = db.query(PC).filter(PC.status == 'changed').count()
    
    # Подсчитываем offline ПК (используем тот же порог - 10 минут)
    offline_threshold = datetime.utcnow() - timedelta(minutes=10)
    offline_pcs = db.query(PC).filter(
        PC.last_seen.isnot(None),
        PC.last_seen < offline_threshold
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


# ==================== Admin API Endpoints (Rooms) ====================

class RoomCreate(PydanticBaseModel):
    name: str
    description: Optional[str] = None

class RoomUpdate(PydanticBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

@app.get("/api/admin/rooms", response_class=JSONResponse)
async def get_rooms(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Получить список всех аудиторий"""
    rooms = db.query(Room).all()
    return {
        "total": len(rooms),
        "items": [room.to_dict() for room in rooms]
    }

@app.get("/api/admin/rooms/{room_id}", response_class=JSONResponse)
async def get_room(
    room_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Получить информацию об аудитории"""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Получаем связанные ПК и камеры
    result = room.to_dict()
    result['pcs'] = [pc.to_dict() for pc in room.pcs]
    result['cameras'] = [camera.to_dict() for camera in room.cameras]
    
    return result

@app.post("/api/admin/rooms", response_class=JSONResponse)
async def create_room(
    room_data: RoomCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Создать новую аудиторию"""
    # Проверяем, не существует ли уже аудитория с таким именем
    existing = db.query(Room).filter(Room.name == room_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Room with this name already exists")
    
    room = Room(
        name=room_data.name,
        description=room_data.description
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    
    return {"message": "Room created", "room": room.to_dict()}

@app.put("/api/admin/rooms/{room_id}", response_class=JSONResponse)
async def update_room(
    room_id: int,
    room_data: RoomUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Обновить информацию об аудитории"""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if room_data.name is not None:
        # Проверяем, не занято ли имя другой аудиторией
        existing = db.query(Room).filter(Room.name == room_data.name, Room.id != room_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Room with this name already exists")
        room.name = room_data.name
    
    if room_data.description is not None:
        room.description = room_data.description
    
    db.commit()
    db.refresh(room)
    
    return {"message": "Room updated", "room": room.to_dict()}

@app.delete("/api/admin/rooms/{room_id}", response_class=JSONResponse)
async def delete_room(
    room_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Удалить аудиторию"""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Проверяем, есть ли связанные ПК или камеры
    if room.pcs:
        raise HTTPException(status_code=400, detail="Cannot delete room with associated PCs")
    if room.cameras:
        raise HTTPException(status_code=400, detail="Cannot delete room with associated cameras")
    
    db.delete(room)
    db.commit()
    
    return {"message": "Room deleted"}


# ==================== Admin API Endpoints (Cameras) ====================

class CameraCreate(PydanticBaseModel):
    name: str
    room_id: int
    status: Optional[str] = "inactive"
    device_id: Optional[str] = None
    ip_address: Optional[str] = None

class CameraUpdate(PydanticBaseModel):
    name: Optional[str] = None
    room_id: Optional[int] = None
    status: Optional[str] = None
    device_id: Optional[str] = None
    ip_address: Optional[str] = None

@app.get("/api/admin/cameras", response_class=JSONResponse)
async def get_cameras(
    request: Request,
    room_id: Optional[int] = None,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Получить список всех камер"""
    query = db.query(Camera)
    
    if room_id:
        query = query.filter(Camera.room_id == room_id)
    
    cameras = query.all()
    return {
        "total": len(cameras),
        "items": [camera.to_dict() for camera in cameras]
    }

@app.get("/api/admin/cameras/{camera_id}", response_class=JSONResponse)
async def get_camera(
    camera_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Получить информацию о камере"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    result = camera.to_dict()
    result['room'] = camera.room.to_dict() if camera.room else None
    
    return result

@app.post("/api/admin/cameras", response_class=JSONResponse)
async def create_camera(
    camera_data: CameraCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Создать новую камеру"""
    # Проверяем, существует ли аудитория
    room = db.query(Room).filter(Room.id == camera_data.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Проверяем статус
    if camera_data.status not in ['active', 'inactive', 'error']:
        raise HTTPException(status_code=400, detail="Invalid status. Must be: active, inactive, or error")
    
    camera = Camera(
        name=camera_data.name,
        room_id=camera_data.room_id,
        status=camera_data.status or 'inactive',
        device_id=camera_data.device_id,
        ip_address=camera_data.ip_address
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    
    return {"message": "Camera created", "camera": camera.to_dict()}

@app.put("/api/admin/cameras/{camera_id}", response_class=JSONResponse)
async def update_camera(
    camera_id: int,
    camera_data: CameraUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Обновить информацию о камере"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    if camera_data.name is not None:
        camera.name = camera_data.name
    
    if camera_data.room_id is not None:
        # Проверяем, существует ли аудитория
        room = db.query(Room).filter(Room.id == camera_data.room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        camera.room_id = camera_data.room_id
    
    if camera_data.status is not None:
        if camera_data.status not in ['active', 'inactive', 'error']:
            raise HTTPException(status_code=400, detail="Invalid status. Must be: active, inactive, or error")
        camera.status = camera_data.status
    
    if camera_data.device_id is not None:
        camera.device_id = camera_data.device_id
    
    if camera_data.ip_address is not None:
        camera.ip_address = camera_data.ip_address
    
    db.commit()
    db.refresh(camera)
    
    return {"message": "Camera updated", "camera": camera.to_dict()}

@app.delete("/api/admin/cameras/{camera_id}", response_class=JSONResponse)
async def delete_camera(
    camera_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Удалить камеру"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    db.delete(camera)
    db.commit()
    
    return {"message": "Camera deleted"}


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


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    admin_user: User = Depends(require_admin)
):
    """Страница админ-панели"""
    template = templates.get_template("admin.html")
    return HTMLResponse(template.render(request=request, user=admin_user))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    """Страница входа"""
    # Проверяем, есть ли уже активная сессия
    from auth import get_user_from_token
    
    session_token = request.cookies.get("session_token")
    if session_token:
        user = get_user_from_token(session_token, db)
        if user:
            return RedirectResponse(url="/", status_code=303)
    
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

@app.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_token")
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

