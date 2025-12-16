"""
Обработчик уведомлений через Email
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional


class EmailHandler:
    """Обработчик для отправки уведомлений через Email"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Настройки SMTP
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        raw_email_from = os.getenv('EMAIL_FROM')
        self.email_from = raw_email_from if raw_email_from else self.smtp_user
        self.email_to = os.getenv('EMAIL_TO', '').split(',') if os.getenv('EMAIL_TO') else []

        # Если EMAIL_FROM не валидный email — подменяем на SMTP_USER
        if self.email_from and '@' not in self.email_from:
            self.logger.warning(f"EMAIL_FROM='{self.email_from}' не выглядит как email, используем SMTP_USER")
            self.email_from = self.smtp_user
        
        # Email включен, если есть настройки SMTP (получатели могут быть из правил)
        self.enabled = bool(
            self.smtp_user and 
            self.smtp_password
        )
        
        if not self.enabled:
            self.logger.debug("Email уведомления отключены (нет настроек SMTP: SMTP_USER или SMTP_PASSWORD)")
        else:
            self.logger.info(f"Email уведомления включены (SMTP: {self.smtp_host}:{self.smtp_port}, от: {self.email_from})")
    
    def is_enabled(self) -> bool:
        """Проверить, включены ли Email уведомления"""
        return self.enabled
    
    def send(self, message: str, subject: str, recipients: Optional[List[str]] = None) -> bool:
        """
        Отправить сообщение по Email
        
        Args:
            message: Текст сообщения
            subject: Тема письма
            recipients: Список получателей (если None - используются настройки по умолчанию)
            
        Returns:
            True если успешно отправлено, False в противном случае
        """
        if not self.enabled:
            return False
        
        # Используем получателей из параметра или настройки по умолчанию
        email_to = recipients if recipients else self.email_to
        
        if not email_to:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = ', '.join(email_to)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            self.logger.info(f"Уведомление отправлено по Email: {', '.join(email_to)}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка отправки Email: {e}", exc_info=True)
            return False




