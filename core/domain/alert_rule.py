"""
Domain модели для правил уведомлений
Бизнес-логика правил уведомлений
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class AlertRuleFilter:
    """Фильтр для правила уведомлений"""
    # Фильтры по локации
    buildings: Optional[List[str]] = None  # Список корпусов (если None - все)
    floors: Optional[List[str]] = None  # Список этажей (если None - все)
    locations: Optional[List[str]] = None  # Список локаций (если None - все)
    
    # Фильтры по компонентам
    component_types: Optional[List[str]] = None  # motherboard, cpu, ram, storage, gpu, network, psu, peripherals
    event_types: Optional[List[str]] = None  # removed, added, replaced
    
    # Исключения (компоненты, которые не должны триггерить уведомление)
    exclude_component_types: Optional[List[str]] = None  # Например, ["peripherals"] для исключения клавиатур/мышей
    
    def matches(
        self,
        building: Optional[str],
        floor: Optional[str],
        location: Optional[str],
        component_type: str,
        event_type: str
    ) -> bool:
        """
        Проверить, соответствует ли событие фильтру
        
        Args:
            building: Корпус ПК
            floor: Этаж ПК
            location: Локация ПК
            component_type: Тип компонента
            event_type: Тип события
            
        Returns:
            True если событие соответствует фильтру
        """
        # Проверка исключений
        if self.exclude_component_types and component_type in self.exclude_component_types:
            return False
        
        # Проверка компонентов
        if self.component_types and component_type not in self.component_types:
            return False
        
        # Проверка типов событий
        if self.event_types and event_type not in self.event_types:
            return False
        
        # Проверка локации
        if self.buildings:
            if not building or building not in self.buildings:
                return False
        
        if self.floors:
            if not floor or floor not in self.floors:
                return False
        
        if self.locations:
            if not location or location not in self.locations:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            'buildings': self.buildings,
            'floors': self.floors,
            'locations': self.locations,
            'component_types': self.component_types,
            'event_types': self.event_types,
            'exclude_component_types': self.exclude_component_types
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlertRuleFilter':
        """Создать из словаря"""
        return cls(
            buildings=data.get('buildings'),
            floors=data.get('floors'),
            locations=data.get('locations'),
            component_types=data.get('component_types'),
            event_types=data.get('event_types'),
            exclude_component_types=data.get('exclude_component_types')
        )


@dataclass
class AlertRule:
    """Правило уведомлений"""
    id: Optional[int] = None
    name: str = ""
    user_id: Optional[int] = None
    enabled: bool = True
    channels: List[str] = None  # ["email", "telegram"]
    filters: Optional[AlertRuleFilter] = None
    recipients: List[str] = None  # Список email/telegram ID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = ["email"]
        if self.recipients is None:
            self.recipients = []
    
    def matches(
        self,
        building: Optional[str],
        floor: Optional[str],
        location: Optional[str],
        component_type: str,
        event_type: str
    ) -> bool:
        """
        Проверить, соответствует ли событие правилу
        
        Args:
            building: Корпус ПК
            floor: Этаж ПК
            location: Локация ПК
            component_type: Тип компонента
            event_type: Тип события
            
        Returns:
            True если событие соответствует правилу
        """
        if not self.enabled:
            return False
        
        if not self.filters:
            # Если фильтров нет - правило срабатывает на все события
            return True
        
        return self.filters.matches(building, floor, location, component_type, event_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'user_id': self.user_id,
            'enabled': self.enabled,
            'channels': self.channels,
            'filters': self.filters.to_dict() if self.filters else None,
            'recipients': self.recipients,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlertRule':
        """Создать из словаря"""
        filters = None
        if data.get('filters'):
            filters = AlertRuleFilter.from_dict(data['filters'])
        
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            user_id=data.get('user_id'),
            enabled=data.get('enabled', True),
            channels=data.get('channels', ['email']),
            filters=filters,
            recipients=data.get('recipients', []),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )

