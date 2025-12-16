"""
Unit of Work паттерн для управления транзакциями и репозиториями
Централизует управление сессией БД и предоставляет единую точку доступа к репозиториям
"""
from typing import Optional
from contextlib import contextmanager
from sqlalchemy.orm import Session

from infrastructure.database.session import SessionLocal
from infrastructure.database.repositories.pc_repository import PCRepository
from infrastructure.database.repositories.config_repository import ConfigRepository
from infrastructure.database.repositories.current_config_repository import CurrentConfigRepository
from infrastructure.database.repositories.event_repository import EventRepository
from infrastructure.database.repositories.alert_rule_repository import AlertRuleRepository


class UnitOfWork:
    """
    Unit of Work для управления транзакциями и репозиториями
    
    Предоставляет:
    - Единую сессию БД для всех операций
    - Доступ ко всем репозиториям
    - Управление транзакциями (commit/rollback)
    - Context manager для автоматического управления жизненным циклом
    """
    
    def __init__(self, session: Optional[Session] = None):
        """
        Инициализация Unit of Work
        
        Args:
            session: Существующая сессия БД (опционально, для тестирования)
        """
        self._session: Optional[Session] = session
        self._should_close = session is None
        
        # Репозитории (lazy initialization)
        self._pc_repository: Optional[PCRepository] = None
        self._config_repository: Optional[ConfigRepository] = None
        self._current_config_repository: Optional[CurrentConfigRepository] = None
        self._event_repository: Optional[EventRepository] = None
        self._alert_rule_repository: Optional[AlertRuleRepository] = None
    
    @property
    def session(self) -> Session:
        """Получить сессию БД (создает при первом обращении)"""
        if self._session is None:
            self._session = SessionLocal()
        return self._session
    
    @property
    def pc_repository(self) -> PCRepository:
        """Репозиторий для работы с ПК"""
        if self._pc_repository is None:
            self._pc_repository = PCRepository(self.session)
        return self._pc_repository
    
    @property
    def config_repository(self) -> ConfigRepository:
        """Репозиторий для работы с конфигурациями"""
        if self._config_repository is None:
            self._config_repository = ConfigRepository(self.session)
        return self._config_repository
    
    @property
    def current_config_repository(self) -> CurrentConfigRepository:
        """Репозиторий для работы с текущими конфигурациями"""
        if self._current_config_repository is None:
            self._current_config_repository = CurrentConfigRepository(self.session)
        return self._current_config_repository
    
    @property
    def event_repository(self) -> EventRepository:
        """Репозиторий для работы с событиями"""
        if self._event_repository is None:
            self._event_repository = EventRepository(self.session)
        return self._event_repository
    
    @property
    def alert_rule_repository(self) -> AlertRuleRepository:
        """Репозиторий для работы с правилами уведомлений"""
        if self._alert_rule_repository is None:
            self._alert_rule_repository = AlertRuleRepository(self.session)
        return self._alert_rule_repository
    
    def commit(self) -> None:
        """Закоммитить транзакцию"""
        if self._session:
            self._session.commit()
    
    def rollback(self) -> None:
        """Откатить транзакцию"""
        if self._session:
            self._session.rollback()
    
    def flush(self) -> None:
        """Выполнить flush (без commit)"""
        if self._session:
            self._session.flush()
    
    def close(self) -> None:
        """Закрыть сессию"""
        if self._session and self._should_close:
            self._session.close()
            self._session = None
    
    def __enter__(self):
        """Вход в context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из context manager"""
        # Управление транзакцией выполняется в unit_of_work context manager
        # Здесь только закрываем сессию
        self.close()
        return False  # Не подавляем исключения


@contextmanager
def unit_of_work(session: Optional[Session] = None):
    """
    Context manager для Unit of Work
    
    Использование:
        with unit_of_work() as uow:
            pc = uow.pc_repository.find_by_id("pc123")
            uow.commit()
    
    Args:
        session: Существующая сессия БД (опционально)
    
    Yields:
        UnitOfWork экземпляр
    """
    uow = UnitOfWork(session=session)
    try:
        yield uow
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        uow.close()

