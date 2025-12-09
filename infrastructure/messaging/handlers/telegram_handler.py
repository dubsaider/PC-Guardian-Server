"""
Обработчик уведомлений через Telegram
"""
import os
import logging
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


class TelegramHandler:
    """Обработчик для отправки уведомлений через Telegram"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            self.logger.debug("Telegram уведомления отключены (нет токена или chat_id)")
    
    def is_enabled(self) -> bool:
        """Проверить, включены ли Telegram уведомления"""
        return self.enabled
    
    def send(self, message: str) -> bool:
        """
        Отправить сообщение в Telegram
        
        Args:
            message: Текст сообщения
            
        Returns:
            True если успешно отправлено, False в противном случае
        """
        if not self.enabled:
            return False
        
        if not requests:
            self.logger.warning("Библиотека requests не установлена, Telegram уведомления недоступны")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            self.logger.info("Уведомление отправлено в Telegram")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка отправки в Telegram: {e}")
            return False



