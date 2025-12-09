"""
Утилита для парсинга локаций
Парсит название аудитории (например, D752) и извлекает корпус и этаж
"""
import re
from typing import Optional, Tuple


def parse_location(location: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Парсит локацию и извлекает корпус и этаж
    
    Примеры:
    - "D752" -> building="D", floor="7", location="D752"
    - "площадка ICPC" -> building=None, floor=None, location="площадка ICPC"
    - "A123" -> building="A", floor="1", location="A123"
    
    Args:
        location: Название локации (аудитория или зона)
        
    Returns:
        Tuple[location, building, floor]
    """
    if not location:
        return None, None, None
    
    location = location.strip()
    if not location:
        return None, None, None
    
    # Паттерн для аудиторий типа D752, A123 и т.д.
    # Первая буква - корпус, первая цифра - этаж
    pattern = r'^([A-ZА-ЯЁ])(\d)'
    match = re.match(pattern, location, re.IGNORECASE)
    
    if match:
        building = match.group(1).upper()
        floor = match.group(2)
        return location, building, floor
    
    # Если не подходит под паттерн (например, "площадка ICPC"), возвращаем как есть
    return location, None, None


def update_pc_location(pc, location: Optional[str]):
    """
    Обновляет локацию ПК и парсит корпус/этаж
    
    Args:
        pc: Объект PC
        location: Название локации
    """
    parsed_location, building, floor = parse_location(location)
    pc.location = parsed_location
    pc.building = building
    pc.floor = floor

