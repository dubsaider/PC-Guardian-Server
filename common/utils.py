"""
Утилиты для работы с данными
"""
from typing import Optional, List, Dict, Any
import logging


def normalize_search_fields(
    building: Optional[str] = None,
    floor: Optional[str] = None,
    location: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """
    Нормализует поисковые поля (приводит к нижнему регистру для регистронезависимого поиска)
    
    Returns:
        Словарь с нормализованными полями
    """
    return {
        'building': building.lower().strip() if building else None,
        'floor': floor.lower().strip() if floor else None,
        'location': location.lower().strip() if location else None,
        'search': search.lower().strip() if search else None
    }


def extract_ip_addresses_from_config(current_config) -> List[str]:
    """
    Извлекает IPv4 адреса из текущей конфигурации
    
    Args:
        current_config: Объект PCCurrentConfiguration
        
    Returns:
        Список IPv4 адресов (без дубликатов, до 3 адресов)
    """
    ip_addresses = []
    if current_config and current_config.network_adapters:
        try:
            network_data = current_config.get_component('network_adapters')
            if network_data and isinstance(network_data, list):
                for adapter in network_data:
                    if isinstance(adapter, dict):
                        adapter_ips = adapter.get('ip_addresses', [])
                        if adapter_ips:
                            # Фильтруем только IPv4 адреса (без IPv6)
                            for ip in adapter_ips:
                                if ':' not in ip:  # IPv4 не содержит двоеточий
                                    ip_addresses.append(ip)
        except Exception as e:
            # Логируем ошибку для отладки
            logger = logging.getLogger(__name__)
            pc_id = getattr(current_config, 'pc_id', 'unknown')
            logger.warning(f"Error parsing network_adapters for {pc_id}: {e}", exc_info=True)
    
    # Убираем дубликаты и берем до 3 адресов
    if ip_addresses:
        unique_ips = list(dict.fromkeys(ip_addresses))[:3]
        return unique_ips
    
    return []


def find_pc_ids_by_ip_search(
    db,
    PCCurrentConfiguration,
    search: str
) -> List[str]:
    """
    Находит PC ID по поисковому запросу в IP-адресах
    
    Args:
        db: SQLAlchemy сессия
        PCCurrentConfiguration: Модель текущей конфигурации
        search: Поисковый запрос (уже нормализован к нижнему регистру)
        
    Returns:
        Список PC ID, у которых IP-адреса содержат подстроку
    """
    matching_pc_ids = []
    
    # Получаем все текущие конфигурации с network_adapters
    current_configs = db.query(PCCurrentConfiguration).filter(
        PCCurrentConfiguration.network_adapters.isnot(None)
    ).all()
    
    # Собираем список PC ID, где IP-адреса содержат подстроку (регистронезависимый поиск)
    for current_config in current_configs:
        try:
            if current_config.network_adapters:
                network_data = current_config.get_component('network_adapters')
                if isinstance(network_data, list):
                    for adapter in network_data:
                        if isinstance(adapter, dict):
                            ip_addresses = adapter.get('ip_addresses', [])
                            if ip_addresses:
                                for ip in ip_addresses:
                                    # search уже в нижнем регистре, приводим IP к нижнему для сравнения
                                    if search in ip.lower():
                                        matching_pc_ids.append(current_config.pc_id)
                                        break
        except:
            continue
    
    return matching_pc_ids







