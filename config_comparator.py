"""
Модуль сравнения конфигураций ПК
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from common.models import ChangeEvent
from database import PCConfiguration as DBPCConfiguration


class ConfigComparator:
    """Класс для сравнения конфигураций ПК"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def compare_configurations(
        self,
        baseline: DBPCConfiguration,
        current: DBPCConfiguration
    ) -> List[ChangeEvent]:
        """
        Сравнить эталонную и текущую конфигурации
        
        Args:
            baseline: Эталонная конфигурация
            current: Текущая конфигурация
            
        Returns:
            Список событий изменений
        """
        events = []
        
        # Сравниваем каждый компонент
        events.extend(self._compare_component('motherboard', baseline, current))
        events.extend(self._compare_component('cpu', baseline, current))
        events.extend(self._compare_ram_modules(baseline, current))
        events.extend(self._compare_storage_devices(baseline, current))
        events.extend(self._compare_component('gpu', baseline, current))
        events.extend(self._compare_network_adapters(baseline, current))
        events.extend(self._compare_component('psu', baseline, current))
        
        return events
    
    def _compare_component(
        self,
        component_name: str,
        baseline: DBPCConfiguration,
        current: DBPCConfiguration
    ) -> List[ChangeEvent]:
        """Сравнить одиночный компонент"""
        events = []
        
        baseline_data = baseline.get_component(component_name)
        current_data = current.get_component(component_name)
        
        # Компонент удален
        if baseline_data and not current_data:
            events.append(ChangeEvent(
                pc_id=baseline.pc_id,
                component_type=component_name,
                event_type='removed',
                old_value=baseline_data,
                new_value=None,
                details=f"Компонент {component_name} удален"
            ))
        
        # Компонент добавлен
        elif not baseline_data and current_data:
            events.append(ChangeEvent(
                pc_id=baseline.pc_id,
                component_type=component_name,
                event_type='added',
                old_value=None,
                new_value=current_data,
                details=f"Компонент {component_name} добавлен"
            ))
        
        # Компонент изменен
        elif baseline_data and current_data:
            if not self._components_equal(baseline_data, current_data):
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type=component_name,
                    event_type='replaced',
                    old_value=baseline_data,
                    new_value=current_data,
                    details=f"Компонент {component_name} заменен"
                ))
        
        return events
    
    def _compare_ram_modules(
        self,
        baseline: DBPCConfiguration,
        current: DBPCConfiguration
    ) -> List[ChangeEvent]:
        """Сравнить модули RAM (могут быть множественные)"""
        events = []
        
        baseline_modules = baseline.get_component('ram_modules') or []
        current_modules = current.get_component('ram_modules') or []
        
        # Создаем словари по серийным номерам и слотам
        baseline_dict = {}
        for module in baseline_modules:
            key = module.get('serial_number') or module.get('slot') or f"slot_{len(baseline_dict)}"
            baseline_dict[key] = module
        
        current_dict = {}
        for module in current_modules:
            key = module.get('serial_number') or module.get('slot') or f"slot_{len(current_dict)}"
            current_dict[key] = module
        
        # Проверяем удаленные модули
        for key, module in baseline_dict.items():
            if key not in current_dict:
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type='ram',
                    event_type='removed',
                    old_value=module,
                    new_value=None,
                    details=f"Модуль RAM удален: {module.get('model', 'неизвестно')} в слоте {module.get('slot', 'неизвестно')}"
                ))
        
        # Проверяем добавленные модули
        for key, module in current_dict.items():
            if key not in baseline_dict:
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type='ram',
                    event_type='added',
                    old_value=None,
                    new_value=module,
                    details=f"Модуль RAM добавлен: {module.get('model', 'неизвестно')} в слоте {module.get('slot', 'неизвестно')}"
                ))
        
        # Проверяем замененные модули
        for key in baseline_dict.keys() & current_dict.keys():
            if not self._components_equal(baseline_dict[key], current_dict[key]):
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type='ram',
                    event_type='replaced',
                    old_value=baseline_dict[key],
                    new_value=current_dict[key],
                    details=f"Модуль RAM заменен в слоте {baseline_dict[key].get('slot', 'неизвестно')}"
                ))
        
        return events
    
    def _compare_storage_devices(
        self,
        baseline: DBPCConfiguration,
        current: DBPCConfiguration
    ) -> List[ChangeEvent]:
        """Сравнить накопители (могут быть множественные)"""
        events = []
        
        baseline_devices = baseline.get_component('storage_devices') or []
        current_devices = current.get_component('storage_devices') or []
        
        # Создаем словари по серийным номерам
        baseline_dict = {}
        for device in baseline_devices:
            key = device.get('serial_number') or f"device_{len(baseline_dict)}"
            baseline_dict[key] = device
        
        current_dict = {}
        for device in current_devices:
            key = device.get('serial_number') or f"device_{len(current_dict)}"
            current_dict[key] = device
        
        # Проверяем удаленные устройства
        for key, device in baseline_dict.items():
            if key not in current_dict:
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type='storage',
                    event_type='removed',
                    old_value=device,
                    new_value=None,
                    details=f"Накопитель удален: {device.get('model', 'неизвестно')}"
                ))
        
        # Проверяем добавленные устройства
        for key, device in current_dict.items():
            if key not in baseline_dict:
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type='storage',
                    event_type='added',
                    old_value=None,
                    new_value=device,
                    details=f"Накопитель добавлен: {device.get('model', 'неизвестно')}"
                ))
        
        # Проверяем замененные устройства
        for key in baseline_dict.keys() & current_dict.keys():
            if not self._components_equal(baseline_dict[key], current_dict[key]):
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type='storage',
                    event_type='replaced',
                    old_value=baseline_dict[key],
                    new_value=current_dict[key],
                    details=f"Накопитель заменен: {baseline_dict[key].get('model', 'неизвестно')}"
                ))
        
        return events
    
    def _compare_network_adapters(
        self,
        baseline: DBPCConfiguration,
        current: DBPCConfiguration
    ) -> List[ChangeEvent]:
        """Сравнить сетевые адаптеры (могут быть множественные)"""
        events = []
        
        baseline_adapters = baseline.get_component('network_adapters') or []
        current_adapters = current.get_component('network_adapters') or []
        
        # Создаем словари по MAC-адресам
        baseline_dict = {adapter.get('mac_address'): adapter for adapter in baseline_adapters}
        current_dict = {adapter.get('mac_address'): adapter for adapter in current_adapters}
        
        # Проверяем удаленные адаптеры
        for mac, adapter in baseline_dict.items():
            if mac not in current_dict:
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type='network',
                    event_type='removed',
                    old_value=adapter,
                    new_value=None,
                    details=f"Сетевой адаптер удален: {adapter.get('name', 'неизвестно')} ({mac})"
                ))
        
        # Проверяем добавленные адаптеры
        for mac, adapter in current_dict.items():
            if mac not in baseline_dict:
                events.append(ChangeEvent(
                    pc_id=baseline.pc_id,
                    component_type='network',
                    event_type='added',
                    old_value=None,
                    new_value=adapter,
                    details=f"Сетевой адаптер добавлен: {adapter.get('name', 'неизвестно')} ({mac})"
                ))
        
        return events
    
    def _components_equal(self, comp1: Dict[str, Any], comp2: Dict[str, Any]) -> bool:
        """Проверить, равны ли два компонента"""
        # Нормализуем словари (убираем None значения для сравнения)
        def normalize(d):
            return {k: v for k, v in d.items() if v is not None}
        
        return normalize(comp1) == normalize(comp2)

