"""
Конфигурация приложения
Централизованное хранение настроек и констант
"""
import os
from typing import Optional


class AppSettings:
    """Настройки приложения"""
    
    def __init__(self):
        # Пороги времени для определения статусов
        self.offline_threshold_minutes: int = int(
            os.getenv("PC_GUARDIAN_OFFLINE_THRESHOLD_MINUTES", "10")
        )
        self.recent_events_days: int = int(
            os.getenv("PC_GUARDIAN_RECENT_EVENTS_DAYS", "7")
        )
        
        # Настройки группировки email уведомлений
        self.email_grouping_window_seconds: int = int(
            os.getenv("EMAIL_GROUPING_WINDOW_SECONDS", "60")
        )
        
        # Безопасность
        self.secret_key: str = os.getenv(
            "SECRET_KEY", "your-secret-key-change-in-production"
        )
        self.algorithm: str = "HS256"
        self.access_token_expire_hours: int = 24


# Глобальный экземпляр настроек
settings = AppSettings()

