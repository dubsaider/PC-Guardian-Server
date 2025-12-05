"""
Модели базы данных для системы PC-Guardian
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import Optional, Dict, Any
import json
import os

# Создаем базовый класс для моделей
Base = declarative_base()

# Настройка подключения к БД
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///pc_guardian.db')
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if 'sqlite' in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Получить сессию БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Room(Base):
    """Модель аудитории"""
    __tablename__ = 'rooms'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    pcs = relationship('PC', backref='room', lazy=True)
    cameras = relationship('Camera', backref='room', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Camera(Base):
    """Модель камеры"""
    __tablename__ = 'cameras'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False, index=True)
    status = Column(String(50), default='inactive')  # active, inactive, error
    device_id = Column(String(255), nullable=True)  # Идентификатор устройства камеры
    ip_address = Column(String(50), nullable=True)  # IP-адрес камеры (если есть)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'room_id': self.room_id,
            'status': self.status,
            'device_id': self.device_id,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class PC(Base):
    """Модель ПК"""
    __tablename__ = 'pcs'
    
    id = Column(Integer, primary_key=True)
    pc_id = Column(String(255), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=True, index=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=True)
    status = Column(String(50), default='unknown')  # unknown, normal, changed, offline
    
    # Связи
    configurations = relationship('PCConfiguration', backref='pc', lazy=True, cascade='all, delete-orphan')
    events = relationship('ChangeEvent', backref='pc', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'pc_id': self.pc_id,
            'hostname': self.hostname,
            'room_id': self.room_id,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'status': self.status
        }


class PCConfiguration(Base):
    """Модель конфигурации ПК"""
    __tablename__ = 'pc_configurations'
    
    id = Column(Integer, primary_key=True)
    pc_id = Column(String(255), ForeignKey('pcs.pc_id'), nullable=False, index=True)
    is_baseline = Column(Boolean, default=False)  # Эталонная конфигурация
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Компоненты (хранятся как JSON)
    motherboard = Column(Text, nullable=True)
    cpu = Column(Text, nullable=True)
    ram_modules = Column(Text, nullable=True)
    storage_devices = Column(Text, nullable=True)
    gpu = Column(Text, nullable=True)
    network_adapters = Column(Text, nullable=True)
    psu = Column(Text, nullable=True)
    
    def set_component(self, component_name: str, data: Optional[Dict[str, Any]]):
        """Установить компонент"""
        json_data = json.dumps(data, ensure_ascii=False) if data else None
        setattr(self, component_name, json_data)
    
    def get_component(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Получить компонент"""
        json_data = getattr(self, component_name)
        if json_data:
            return json.loads(json_data)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        result = {
            'id': self.id,
            'pc_id': self.pc_id,
            'is_baseline': self.is_baseline,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }
        
        for component in ['motherboard', 'cpu', 'ram_modules', 'storage_devices', 'gpu', 'network_adapters', 'psu']:
            result[component] = self.get_component(component)
        
        return result


class ChangeEvent(Base):
    """Модель события изменения конфигурации"""
    __tablename__ = 'change_events'
    
    id = Column(Integer, primary_key=True)
    pc_id = Column(String(255), ForeignKey('pcs.pc_id'), nullable=False, index=True)
    component_type = Column(String(50), nullable=False)  # motherboard, cpu, ram, storage, gpu, network, psu
    event_type = Column(String(50), nullable=False)  # removed, added, replaced
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    details = Column(Text, nullable=True)
    
    # Старое и новое значение (хранятся как JSON)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    
    # Статус уведомления
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, nullable=True)
    
    # Видеофиксация (заготовка для будущей реализации)
    video_recorded = Column(Boolean, default=False)
    video_path = Column(String(500), nullable=True)  # Путь к записанному видео
    video_recorded_at = Column(DateTime, nullable=True)  # Время записи видео
    
    def set_old_value(self, value: Optional[Dict[str, Any]]):
        """Установить старое значение"""
        self.old_value = json.dumps(value, ensure_ascii=False) if value else None
    
    def set_new_value(self, value: Optional[Dict[str, Any]]):
        """Установить новое значение"""
        self.new_value = json.dumps(value, ensure_ascii=False) if value else None
    
    def get_old_value(self) -> Optional[Dict[str, Any]]:
        """Получить старое значение"""
        if self.old_value:
            return json.loads(self.old_value)
        return None
    
    def get_new_value(self) -> Optional[Dict[str, Any]]:
        """Получить новое значение"""
        if self.new_value:
            return json.loads(self.new_value)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            'id': self.id,
            'pc_id': self.pc_id,
            'component_type': self.component_type,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'details': self.details,
            'old_value': self.get_old_value(),
            'new_value': self.get_new_value(),
            'notified': self.notified,
            'notified_at': self.notified_at.isoformat() if self.notified_at else None,
            'video_recorded': self.video_recorded,
            'video_path': self.video_path,
            'video_recorded_at': self.video_recorded_at.isoformat() if self.video_recorded_at else None
        }


class User(Base):
    """Модель пользователя для веб-интерфейса"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='viewer')  # admin, viewer
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }


