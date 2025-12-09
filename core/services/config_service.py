"""
Сервис для работы с конфигурациями ПК
Бизнес-логика обработки конфигураций
"""
import logging
from datetime import datetime
from typing import Optional

from common.models import PCConfiguration
from infrastructure.database.models import (
    PCConfiguration as DBPCConfiguration,
    PCCurrentConfiguration
)


class ConfigService:
    """Сервис для работы с конфигурациями ПК"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_db_configuration(
        self, 
        pc_id: str, 
        config: PCConfiguration, 
        is_baseline: bool = False
    ) -> DBPCConfiguration:
        """
        Создать объект конфигурации для БД из domain модели
        
        Args:
            pc_id: ID ПК
            config: Domain модель конфигурации
            is_baseline: Является ли эталонной конфигурацией
            
        Returns:
            Объект конфигурации для БД
        """
        db_config = DBPCConfiguration(
            pc_id=pc_id,
            is_baseline=is_baseline,
            timestamp=config.timestamp if config.timestamp else datetime.utcnow(),
            agent_version=config.agent_version
        )
        
        # Сохраняем компоненты
        if config.motherboard:
            db_config.set_component('motherboard', config.motherboard.to_dict())
        if config.cpu:
            db_config.set_component('cpu', config.cpu.to_dict())
        if config.ram_modules:
            db_config.set_component('ram_modules', [m.to_dict() for m in config.ram_modules])
        if config.storage_devices:
            db_config.set_component('storage_devices', [s.to_dict() for s in config.storage_devices])
        if config.gpu:
            db_config.set_component('gpu', config.gpu.to_dict())
        if config.network_adapters:
            network_data = [n.to_dict() for n in config.network_adapters]
            db_config.set_component('network_adapters', network_data)
        if config.psu:
            db_config.set_component('psu', config.psu.to_dict())
        if config.peripherals:
            db_config.set_component('peripherals', [p.to_dict() for p in config.peripherals])
        if config.system_info:
            db_config.set_component('system_info', config.system_info.to_dict())
        
        return db_config
    
    def create_current_configuration(
        self,
        pc_id: str,
        config: PCConfiguration
    ) -> PCCurrentConfiguration:
        """
        Создать объект текущего состояния конфигурации из domain модели
        
        Args:
            pc_id: ID ПК
            config: Domain модель конфигурации
            
        Returns:
            Объект текущего состояния конфигурации для БД
        """
        current_config = PCCurrentConfiguration(
            pc_id=pc_id,
            updated_at=config.timestamp if config.timestamp else datetime.utcnow(),
            agent_version=config.agent_version
        )
        
        # Сохраняем компоненты
        if config.motherboard:
            current_config.set_component('motherboard', config.motherboard.to_dict())
        if config.cpu:
            current_config.set_component('cpu', config.cpu.to_dict())
        if config.ram_modules:
            current_config.set_component('ram_modules', [m.to_dict() for m in config.ram_modules])
        if config.storage_devices:
            current_config.set_component('storage_devices', [s.to_dict() for s in config.storage_devices])
        if config.gpu:
            current_config.set_component('gpu', config.gpu.to_dict())
        if config.network_adapters:
            network_data = [n.to_dict() for n in config.network_adapters]
            current_config.set_component('network_adapters', network_data)
        if config.psu:
            current_config.set_component('psu', config.psu.to_dict())
        if config.peripherals:
            current_config.set_component('peripherals', [p.to_dict() for p in config.peripherals])
        if config.system_info:
            current_config.set_component('system_info', config.system_info.to_dict())
        
        
        return current_config



