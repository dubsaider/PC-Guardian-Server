"""
Обработчик уведомлений через Email
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List


class EmailHandler:
    """Обработчик для отправки уведомлений через Email"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Настройки SMTP
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.email_from = os.getenv('EMAIL_FROM', self.smtp_user)
        self.email_to = os.getenv('EMAIL_TO', '').split(',') if os.getenv('EMAIL_TO') else []
        
        self.enabled = bool(
            self.smtp_user and 
            self.smtp_password and 
            self.email_to
        )
        
        if not self.enabled:
            self.logger.debug("Email уведомления отключены (нет настроек SMTP или получателей)")
    
    def is_enabled(self) -> bool:
        """Проверить, включены ли Email уведомления"""
        return self.enabled
    
    def send(self, message: str, subject: str) -> bool:
        """
        Отправить сообщение по Email
        
        Args:
            message: Текст сообщения
            subject: Тема письма
            
        Returns:
            True если успешно отправлено, False в противном случае
        """
        if not self.enabled:
            return False
        
        if not self.email_to:
            return False
        
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
            return True
        except Exception as e:
            self.logger.error(f"Ошибка отправки Email: {e}")
            return False



