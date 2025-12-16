"""
Инфраструктура системы уведомлений - экспорт компонентов
"""
from infrastructure.messaging.notification_service import NotificationService
from infrastructure.messaging.handlers import TelegramHandler, EmailHandler

__all__ = [
    'NotificationService',
    'TelegramHandler',
    'EmailHandler',
]









