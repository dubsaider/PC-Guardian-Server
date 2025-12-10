"""
Обработчик уведомлений через Telegram
"""
import os
import logging
from typing import Optional, List

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
    
    def send(self, message: str, chat_ids: Optional[List[str]] = None) -> bool:
        """
        Отправить сообщение в Telegram
        
        Args:
            message: Текст сообщения
            chat_ids: Список chat_id получателей (если None - используется настройка по умолчанию)
            
        Returns:
            True если успешно отправлено, False в противном случае
        """
        if not self.enabled:
            return False
        
        if not requests:
            self.logger.warning("Библиотека requests не установлена, Telegram уведомления недоступны")
            return False
        
        # Используем chat_ids из параметра или настройку по умолчанию
        chat_ids_to_send = chat_ids if chat_ids else [self.chat_id] if self.chat_id else []
        
        if not chat_ids_to_send:
            return False
        
        success = True
        for chat_id in chat_ids_to_send:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                data = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, json=data, timeout=10)
                response.raise_for_status()
                self.logger.info(f"Уведомление отправлено в Telegram: {chat_id}")
            except Exception as e:
                self.logger.error(f"Ошибка отправки в Telegram для chat_id {chat_id}: {e}")
                success = False
        
        return success




