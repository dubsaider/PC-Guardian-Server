"""
Сервис уведомлений для PC-Guardian
Использует обработчики для отправки через различные каналы
"""
import logging
from typing import Optional

from infrastructure.database.models import PC, ChangeEvent
from infrastructure.messaging.handlers.telegram_handler import TelegramHandler
from infrastructure.messaging.handlers.email_handler import EmailHandler


class NotificationService:
    """Сервис для отправки уведомлений через различные каналы"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Инициализируем обработчики
        self.telegram_handler = TelegramHandler()
        self.email_handler = EmailHandler()
    
    def send_alert(self, pc: PC, event: ChangeEvent):
        """
        Отправить уведомление об изменении через все доступные каналы
        
        Args:
            pc: Объект ПК
            event: Событие изменения
        """
        message = self._format_alert_message(pc, event)
        
        # Отправляем через все доступные каналы
        if self.telegram_handler.is_enabled():
            self.telegram_handler.send(message)
        
        if self.email_handler.is_enabled():
            subject = f"PC-Guardian: Изменение на {pc.hostname}"
            self.email_handler.send(message, subject)
    
    def _format_alert_message(self, pc: PC, event: ChangeEvent) -> str:
        """Форматировать сообщение об изменении"""
        event_type_ru = {
            'removed': 'удален',
            'added': 'добавлен',
            'replaced': 'заменен'
        }
        
        component_type_ru = {
            'motherboard': 'Материнская плата',
            'cpu': 'Процессор',
            'ram': 'Оперативная память',
            'storage': 'Накопитель',
            'gpu': 'Видеокарта',
            'network': 'Сетевой адаптер',
            'psu': 'Блок питания',
            'peripherals': 'Периферийные устройства'
        }
        
        event_type = event_type_ru.get(event.event_type, event.event_type)
        component_type = component_type_ru.get(event.component_type, event.component_type)
        
        message = f"⚠️ ВНИМАНИЕ: Изменение конфигурации ПК\n\n"
        message += f"ПК: {pc.hostname} ({pc.pc_id})\n"
        message += f"Компонент: {component_type}\n"
        message += f"Тип изменения: {event_type}\n"
        message += f"Время: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if event.details:
            message += f"Детали: {event.details}\n\n"
        
        if event.get_old_value():
            old_value = event.get_old_value()
            old_model = old_value.get('model') or old_value.get('name') or 'неизвестно'
            message += f"Было: {old_model}\n"
        
        if event.get_new_value():
            new_value = event.get_new_value()
            new_model = new_value.get('model') or new_value.get('name') or 'неизвестно'
            message += f"Стало: {new_model}\n"
        
        return message



