"""
SQLAlchemy модели базы данных для системы PC-Guardian
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Импортируем Base из session для единой точки создания
from infrastructure.database.session import Base


class PC(Base):
    """Модель ПК"""
    __tablename__ = 'pcs'
    
    id = Column(Integer, primary_key=True)
    pc_id = Column(String(255), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=True)
    status = Column(String(50), default='unknown')  # unknown, normal, changed, offline
    
    # Локация
    location = Column(String(255), nullable=True, index=True)  # Название аудитории или зоны (например, D752 или "площадка ICPC")
    building = Column(String(50), nullable=True, index=True)  # Корпус (парсится из location, например D из D752)
    floor = Column(String(50), nullable=True, index=True)  # Этаж (парсится из location, например 7 из D752)
    
    # Связи
    configurations = relationship('PCConfiguration', backref='pc', lazy=True, cascade='all, delete-orphan')
    events = relationship('ChangeEvent', backref='pc', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'pc_id': self.pc_id,
            'hostname': self.hostname,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'status': self.status,
            'location': self.location,
            'building': self.building,
            'floor': self.floor
        }


class PCCurrentConfiguration(Base):
    """Модель текущего состояния конфигурации ПК (snapshot для быстрого доступа)"""
    __tablename__ = 'pc_current_configurations'
    
    pc_id = Column(String(255), ForeignKey('pcs.pc_id'), primary_key=True, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    agent_version = Column(String(50), nullable=True)  # Версия агента
    
    # Компоненты (хранятся как JSON)
    motherboard = Column(Text, nullable=True)
    cpu = Column(Text, nullable=True)
    ram_modules = Column(Text, nullable=True)
    storage_devices = Column(Text, nullable=True)
    gpu = Column(Text, nullable=True)
    network_adapters = Column(Text, nullable=True)
    psu = Column(Text, nullable=True)
    peripherals = Column(Text, nullable=True)
    system_info = Column(Text, nullable=True)  # Инфраструктурная информация о системе
    
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
            'pc_id': self.pc_id,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'agent_version': self.agent_version,
        }
        
        for component in ['motherboard', 'cpu', 'ram_modules', 'storage_devices', 'gpu', 'network_adapters', 'psu', 'peripherals', 'system_info']:
            result[component] = self.get_component(component)
        
        return result
    
    @classmethod
    def from_configuration(cls, config: 'PCConfiguration') -> 'PCCurrentConfiguration':
        """Создать текущее состояние из конфигурации истории"""
        current = cls(
            pc_id=config.pc_id,
            updated_at=config.timestamp,
            agent_version=config.agent_version
        )
        
        # Копируем все компоненты
        for component in ['motherboard', 'cpu', 'ram_modules', 'storage_devices', 'gpu', 'network_adapters', 'psu', 'peripherals', 'system_info']:
            component_data = config.get_component(component)
            if component_data:
                current.set_component(component, component_data)
        
        return current


class PCConfiguration(Base):
    """Модель истории изменений конфигурации ПК"""
    __tablename__ = 'pc_configurations'
    
    id = Column(Integer, primary_key=True)
    pc_id = Column(String(255), ForeignKey('pcs.pc_id'), nullable=False, index=True)
    is_baseline = Column(Boolean, default=False)  # Эталонная конфигурация
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)  # Индекс для ускорения запросов
    agent_version = Column(String(50), nullable=True)  # Версия агента
    
    # Компоненты (хранятся как JSON)
    motherboard = Column(Text, nullable=True)
    cpu = Column(Text, nullable=True)
    ram_modules = Column(Text, nullable=True)
    storage_devices = Column(Text, nullable=True)
    gpu = Column(Text, nullable=True)
    network_adapters = Column(Text, nullable=True)
    psu = Column(Text, nullable=True)
    peripherals = Column(Text, nullable=True)
    system_info = Column(Text, nullable=True)  # Инфраструктурная информация о системе
    
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
            'agent_version': self.agent_version,
        }
        
        for component in ['motherboard', 'cpu', 'ram_modules', 'storage_devices', 'gpu', 'network_adapters', 'psu', 'peripherals', 'system_info']:
            result[component] = self.get_component(component)
        
        return result
    
    @classmethod
    def from_current_configuration(cls, current: 'PCCurrentConfiguration') -> 'PCConfiguration':
        """Создать конфигурацию истории из текущего состояния (для сравнения)"""
        config = cls(
            pc_id=current.pc_id,
            is_baseline=False,
            timestamp=current.updated_at,
            agent_version=current.agent_version
        )
        
        # Копируем все компоненты
        for component in ['motherboard', 'cpu', 'ram_modules', 'storage_devices', 'gpu', 'network_adapters', 'psu', 'peripherals', 'system_info']:
            component_data = current.get_component(component)
            if component_data:
                config.set_component(component, component_data)
        
        return config


class ChangeEvent(Base):
    """Модель события изменения конфигурации"""
    __tablename__ = 'change_events'
    
    id = Column(Integer, primary_key=True)
    pc_id = Column(String(255), ForeignKey('pcs.pc_id'), nullable=False, index=True)
    component_type = Column(String(50), nullable=False)  # motherboard, cpu, ram, storage, gpu, network, psu, peripherals
    event_type = Column(String(50), nullable=False)  # removed, added, replaced
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    details = Column(Text, nullable=True)
    
    # Старое и новое значение (хранятся как JSON)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    
    # Статус уведомления
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, nullable=True)
    
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
            'notified_at': self.notified_at.isoformat() if self.notified_at else None
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
