"""
Система оповещений для PC-Guardian
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

from database import PC, ChangeEvent as DBChangeEvent


class NotificationService:
    """Сервис для отправки уведомлений"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Настройки Telegram
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Настройки Email
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.email_from = os.getenv('EMAIL_FROM', self.smtp_user)
        self.email_to = os.getenv('EMAIL_TO', '').split(',') if os.getenv('EMAIL_TO') else []
    
    def send_alert(self, pc: PC, event: DBChangeEvent):
        """
        Отправить уведомление об изменении
        
        Args:
            pc: Объект ПК
            event: Событие изменения
        """
        message = self._format_alert_message(pc, event)
        
        # Отправляем через все доступные каналы
        if self.telegram_bot_token and self.telegram_chat_id:
            self._send_telegram(message)
        
        if self.smtp_user and self.smtp_password and self.email_to:
            self._send_email(message, f"PC-Guardian: Изменение на {pc.hostname}")
    
    def _format_alert_message(self, pc: PC, event: DBChangeEvent) -> str:
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
            'psu': 'Блок питания'
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
        
        if event.old_value:
            old_model = event.old_value.get('model') or event.old_value.get('name') or 'неизвестно'
            message += f"Было: {old_model}\n"
        
        if event.new_value:
            new_model = event.new_value.get('model') or event.new_value.get('name') or 'неизвестно'
            message += f"Стало: {new_model}\n"
        
        return message
    
    def _send_telegram(self, message: str):
        """Отправить уведомление в Telegram"""
        if not requests:
            self.logger.warning("Библиотека requests не установлена, Telegram уведомления недоступны")
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            self.logger.info("Уведомление отправлено в Telegram")
        except Exception as e:
            self.logger.error(f"Ошибка отправки в Telegram: {e}")
    
    def _send_email(self, message: str, subject: str):
        """Отправить уведомление по Email"""
        if not self.email_to:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = ', '.join(self.email_to)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            self.logger.info(f"Уведомление отправлено по Email: {', '.join(self.email_to)}")
        except Exception as e:
            self.logger.error(f"Ошибка отправки Email: {e}")

