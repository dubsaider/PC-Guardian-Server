"""
Сервис уведомлений для PC-Guardian
Использует обработчики для отправки через различные каналы
Логика проверки правил вынесена в AlertService
"""
import logging
from typing import Optional, List
from datetime import datetime, timezone

from infrastructure.database.models import PC, ChangeEvent, AlertRule as DBAlertRule
from infrastructure.messaging.handlers.telegram_handler import TelegramHandler
from infrastructure.messaging.handlers.email_handler import EmailHandler
from core.services.alert_service import AlertService


class NotificationService:
    """Сервис для отправки уведомлений через различные каналы"""
    
    def __init__(self, alert_service: Optional[AlertService] = None):
        self.logger = logging.getLogger(__name__)
        self.alert_service = alert_service
        
        # Инициализируем обработчики
        self.telegram_handler = TelegramHandler()
        self.email_handler = EmailHandler()
    
    def send_alert(self, pc: PC, event: ChangeEvent, user_id: Optional[int] = None):
        """
        Отправить уведомление об изменении согласно правилам
        
        Args:
            pc: Объект ПК
            event: Событие изменения
            user_id: ID пользователя (для фильтрации правил)
        """
        message = self._format_alert_message(pc, event)
        subject = f"PC-Guardian: {pc.hostname} — {event.event_type}"
        
        # Если есть сервис правил - используем его
        if self.alert_service:
            matching_rules = self.alert_service.get_matching_rules(pc, event, user_id)
            
            if not matching_rules:
                self.logger.debug(f"Нет правил уведомлений для события {event.id}")
                return
            
            # Отправляем уведомления согласно правилам
            for rule in matching_rules:
                channels = rule.get_channels()
                recipients = rule.get_recipients()
                
                if 'email' in channels:
                    email_recipients = [r for r in recipients if '@' in r]  # Фильтруем email адреса
                    if email_recipients:
                        self.email_handler.send(message, subject, email_recipients)
                
                if 'telegram' in channels:
                    telegram_recipients = [r for r in recipients if '@' not in r]  # Фильтруем telegram chat_id
                    if telegram_recipients:
                        self.telegram_handler.send(message, telegram_recipients)
            
            # Помечаем событие как уведомленное
            event.notified = True
            event.notified_at = datetime.utcnow()
        else:
            # Fallback: отправляем через все доступные каналы (старое поведение)
            if self.telegram_handler.is_enabled():
                self.telegram_handler.send(message)
            
            if self.email_handler.is_enabled():
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
        
        # Время с учетом локальной таймзоны
        event_time_local = event.timestamp
        if event_time_local:
            if event_time_local.tzinfo is None:
                event_time_local = event_time_local.replace(tzinfo=timezone.utc)
            local_tz = datetime.now().astimezone().tzinfo
            event_time_local = event_time_local.astimezone(local_tz)
            time_str = event_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')
        else:
            time_str = "неизвестно"

        # Локация
        location_lines = []
        if pc.location:
            location_lines.append(f"Локация: {pc.location}")
        if pc.building:
            location_lines.append(f"Корпус: {pc.building}")
        if pc.floor:
            location_lines.append(f"Этаж: {pc.floor}")
        location_block = "\n".join(location_lines) if location_lines else "Локация: не указана"

        message = (
            "⚠️ ВНИМАНИЕ: Изменение конфигурации ПК\n\n"
            f"ПК: {pc.hostname} ({pc.pc_id})\n"
            f"{location_block}\n"
            f"Компонент: {component_type}\n"
            f"Тип изменения: {event_type}\n"
            f"Время: {time_str}\n\n"
        )
        
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




